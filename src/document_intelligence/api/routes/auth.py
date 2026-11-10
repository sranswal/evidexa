"""Authentication and Case Membership REST API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from document_intelligence.api.csrf import generate_csrf_token, set_csrf_cookie
from document_intelligence.api.dependencies import (
    get_auth_service,
    get_case_access_service,
    get_current_user,
    require_case_access,
)
from document_intelligence.core.config import settings
from document_intelligence.domain.models.auth import (
    AddCaseMemberRequest,
    CaseMemberResponse,
    CaseRole,
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    User,
)
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.modules.auth.service import AuthenticationService, CaseAccessService

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])
members_router = APIRouter(prefix="/cases/{case_id}/members", tags=["Case Memberships & RBAC"])


def _set_auth_cookies(response: Response, tokens: TokenResponse) -> None:
    """Set HttpOnly secure cookies for access and refresh tokens, plus CSRF cookie."""
    # Access token cookie (short-lived)
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        max_age=tokens.expires_in,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    # Refresh token cookie (long-lived)
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        max_age=int(settings.refresh_token_expire_days * 86400),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    # CSRF cookie (double-submit, readable by client JS)
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)


def _clear_auth_cookies(response: Response) -> None:
    """Clear authentication session cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="csrf_token", path="/")


@router.get("/csrf-token", status_code=status.HTTP_200_OK)
def get_csrf_token(response: Response) -> dict[str, str]:
    """Issue a fresh CSRF token and set the csrf_token cookie."""
    token = generate_csrf_token()
    set_csrf_cookie(response, token)
    return {"csrf_token": token}


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate user with username or email and issue short-lived access and refresh tokens."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    tokens = service.authenticate_user(
        username_or_email=payload.username_or_email,
        password=payload.password,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    _set_auth_cookies(response, tokens)
    return tokens


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> User:
    """Register a new user account with Argon2id password hashing."""
    return service.register_user(
        email=payload.email,
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
    )


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def refresh_token(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    service: AuthenticationService = Depends(get_auth_service),
) -> TokenResponse:
    """Rotate refresh token and issue a fresh access token."""
    raw_token = (payload.refresh_token if payload else None) or request.cookies.get("refresh_token")
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    tokens = service.refresh_tokens(
        raw_refresh_token=raw_token or "",
        ip_address=client_ip,
        user_agent=user_agent,
    )
    _set_auth_cookies(response, tokens)
    return tokens


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    service: AuthenticationService = Depends(get_auth_service),
) -> dict[str, str]:
    """Revoke active refresh token and invalidate authentication session."""
    raw_token = (payload.refresh_token if payload else None) or request.cookies.get("refresh_token")
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    service.logout(
        raw_refresh_token=raw_token,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    _clear_auth_cookies(response)
    return {"status": "logged_out", "message": "Session invalidated successfully."}


@router.get("/me", response_model=User, status_code=status.HTTP_200_OK)
def get_current_user_profile(
    current_user: UserModel = Depends(get_current_user),
) -> User:
    """Retrieve authenticated user identity and profile."""
    return User.model_validate(current_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    current_user: UserModel = Depends(get_current_user),
    service: AuthenticationService = Depends(get_auth_service),
) -> dict[str, str]:
    """Change authenticated user password and invalidate all active sessions."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    service.change_password(
        user_id=current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    _clear_auth_cookies(response)
    return {
        "status": "password_changed",
        "message": "Password changed successfully. All active sessions have been invalidated.",
    }


# -----------------------------------------------------------------------------
# Case Memberships Management
# -----------------------------------------------------------------------------


@members_router.get("", response_model=list[CaseMemberResponse])
def list_case_members(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: CaseAccessService = Depends(get_case_access_service),
) -> list[CaseMemberResponse]:
    """List members and their assigned RBAC roles for a case workspace."""
    memberships = service.repo.list_case_memberships(case_id)
    result: list[CaseMemberResponse] = []
    for m in memberships:
        u = service.repo.get_user_by_id(m.user_id)
        if u:
            result.append(
                CaseMemberResponse(
                    id=m.id,
                    case_id=m.case_id,
                    user_id=u.id,
                    username=u.username,
                    email=u.email,
                    full_name=u.full_name,
                    role=CaseRole(m.role),
                    assigned_by=m.assigned_by,
                    created_at=m.created_at,
                )
            )
    return result


@members_router.post("", response_model=CaseMemberResponse, status_code=status.HTTP_201_CREATED)
def add_or_update_case_member(
    case_id: str,
    payload: AddCaseMemberRequest,
    current_user: UserModel = Depends(get_current_user),
    service: CaseAccessService = Depends(get_case_access_service),
) -> CaseMemberResponse:
    """Assign or update a user's RBAC role in a case workspace (Requires Case ADMIN role)."""
    membership = service.add_case_member(
        case_id=case_id,
        target_user_id=payload.user_id,
        role=payload.role,
        actor_user=current_user,
    )
    u = service.repo.get_user_by_id(membership.user_id)
    assert u is not None
    return CaseMemberResponse(
        id=membership.id,
        case_id=membership.case_id,
        user_id=u.id,
        username=u.username,
        email=u.email,
        full_name=u.full_name,
        role=CaseRole(membership.role),
        assigned_by=membership.assigned_by,
        created_at=membership.created_at,
    )


@members_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_case_member(
    case_id: str,
    user_id: str,
    current_user: UserModel = Depends(get_current_user),
    service: CaseAccessService = Depends(get_case_access_service),
) -> None:
    """Revoke user membership from a case workspace (Requires Case ADMIN role)."""
    service.remove_case_member(
        case_id=case_id,
        target_user_id=user_id,
        actor_user=current_user,
    )
