"""Authentication and Case RBAC authorization services."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, timedelta
from typing import Any

from document_intelligence.core.exceptions import (
    AuthenticationException,
    ForbiddenException,
    NotFoundException,
    RateLimitException,
    ValidationException,
)
from document_intelligence.domain.enums import CaseStatus
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.auth import (
    AuthEventType,
    CaseRole,
    SystemRole,
    TokenResponse,
    User,
)
from document_intelligence.infrastructure.persistence.models import (
    AuthenticationEventModel,
    CaseMembershipModel,
    RefreshTokenModel,
    UserModel,
)
from document_intelligence.infrastructure.repositories.auth_repository import AuthRepository
from document_intelligence.modules.auth.password import PasswordService
from document_intelligence.modules.auth.rate_limiter import AuthRateLimiter, auth_rate_limiter
from document_intelligence.modules.auth.tokens import TokenService

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Enterprise authentication lifecycle manager."""

    def __init__(
        self,
        repo: AuthRepository,
        token_service: TokenService | None = None,
        password_service: PasswordService | None = None,
        rate_limiter: AuthRateLimiter | None = None,
    ) -> None:
        self.repo = repo
        self.token_service = token_service or TokenService()
        self.password_service = password_service or PasswordService()
        self.rate_limiter = rate_limiter or auth_rate_limiter
        self._refresh_lock = threading.Lock()

    def register_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str,
        system_role: SystemRole = SystemRole.USER,
    ) -> User:
        """Register a new user account with Argon2id password hashing."""
        email_clean = email.strip().lower()
        username_clean = username.strip().lower()

        if self.repo.get_user_by_email(email_clean):
            raise ValidationException(f"Email '{email_clean}' is already registered.")
        if self.repo.get_user_by_username(username_clean):
            raise ValidationException(f"Username '{username_clean}' is already taken.")
        if len(password) < 8:
            raise ValidationException("Password must be at least 8 characters long.")

        hashed_pw = self.password_service.hash_password(password)
        now = utc_now()
        user_model = UserModel(
            id=generate_id(),
            email=email_clean,
            username=username_clean,
            hashed_password=hashed_pw,
            full_name=full_name.strip(),
            is_active=True,
            system_role=system_role.value,
            created_at=now,
            updated_at=now,
        )
        created = self.repo.create_user(user_model)

        # Automatically join default organization
        default_org = self.repo.get_or_create_default_org()
        self.repo.add_org_membership(default_org.id, created.id, role="MEMBER")

        return User.model_validate(created)

    def authenticate_user(
        self,
        username_or_email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Authenticate user credentials, enforce rate limits, and issue tokens."""
        rate_key = f"{ip_address or 'unknown'}:{username_or_email.strip().lower()}"

        if self.rate_limiter.is_rate_limited(rate_key):
            remaining = self.rate_limiter.get_remaining_lockout_seconds(rate_key)
            self._log_event(
                user_id=None,
                event_type=AuthEventType.ACCESS_DENIED,
                username=username_or_email,
                ip=ip_address,
                ua=user_agent,
                details={"reason": "Rate limit exceeded", "lockout_seconds": remaining},
            )
            raise RateLimitException(
                f"Too many failed login attempts. Account temporarily locked. Try again in {remaining} seconds.",
                details={"lockout_seconds": remaining},
            )

        user = self.repo.get_user_by_identifier(username_or_email)
        if not user or not self.password_service.verify_password(password, user.hashed_password):
            self.rate_limiter.record_failure(rate_key)
            self._log_event(
                user_id=user.id if user else None,
                event_type=AuthEventType.LOGIN_FAILED,
                username=username_or_email,
                ip=ip_address,
                ua=user_agent,
                details={"reason": "Invalid credentials"},
            )
            # Generic constant-time failure message
            raise AuthenticationException("Invalid username or password.")

        if not user.is_active:
            self._log_event(
                user_id=user.id,
                event_type=AuthEventType.ACCESS_DENIED,
                username=username_or_email,
                ip=ip_address,
                ua=user_agent,
                details={"reason": "Account disabled"},
            )
            raise AuthenticationException("User account is disabled.")

        # Reset rate limiter upon success
        self.rate_limiter.record_success(rate_key)

        # Issue access token
        access_token, expires_in = self.token_service.create_access_token(
            user_id=user.id,
            email=user.email,
            username=user.username,
            system_role=user.system_role,
        )

        # Issue opaque refresh token
        raw_refresh = self.token_service.create_refresh_token()
        hashed_refresh = self.token_service.hash_refresh_token(raw_refresh)
        refresh_exp = utc_now() + timedelta(days=self.token_service.refresh_token_expire_days)

        token_model = RefreshTokenModel(
            id=generate_id(),
            user_id=user.id,
            token_hash=hashed_refresh,
            expires_at=refresh_exp,
            is_revoked=False,
            created_at=utc_now(),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.repo.store_refresh_token(token_model)

        self._log_event(
            user_id=user.id,
            event_type=AuthEventType.LOGIN_SUCCESS,
            username=user.username,
            ip=ip_address,
            ua=user_agent,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=expires_in,
            user=User.model_validate(user),
        )

    def refresh_tokens(
        self,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Rotate refresh token atomically and issue a fresh access token with reuse detection."""
        if not raw_refresh_token:
            raise AuthenticationException("Refresh token is required.")

        with self._refresh_lock:
            hashed = self.token_service.hash_refresh_token(raw_refresh_token)
            token_model = self.repo.get_refresh_token_by_hash(hashed)

            if not token_model:
                raise AuthenticationException("Invalid refresh token.")

            # Detect refresh token reuse breach
            if token_model.is_revoked:
                # Immediate incident response: invalidate all active sessions for this user family
                revoked_count = self.repo.revoke_all_user_tokens(token_model.user_id)
                self._log_event(
                    user_id=token_model.user_id,
                    event_type=AuthEventType.REFRESH_REUSE_DETECTED,
                    ip=ip_address,
                    ua=user_agent,
                    details={
                        "compromised_token_id": token_model.id,
                        "revoked_sessions_count": revoked_count,
                    },
                )
                raise AuthenticationException(
                    "Security alert: Refresh token reuse detected. All active sessions have been invalidated."
                )

            now = utc_now()
            expires_at = token_model.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at < now:
                self.repo.revoke_refresh_token(token_model)
                raise AuthenticationException("Refresh token has expired.")

            user = self.repo.get_user_by_id(token_model.user_id)
            if not user or not user.is_active:
                self.repo.revoke_refresh_token(token_model)
                raise AuthenticationException("User account is inactive or deleted.")

            # Generate new refresh token
            new_raw_refresh = self.token_service.create_refresh_token()
            new_hashed = self.token_service.hash_refresh_token(new_raw_refresh)
            refresh_exp = now + timedelta(days=self.token_service.refresh_token_expire_days)

            new_token_model = RefreshTokenModel(
                id=generate_id(),
                user_id=user.id,
                token_hash=new_hashed,
                expires_at=refresh_exp,
                is_revoked=False,
                created_at=now,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self.repo.store_refresh_token(new_token_model)

            # Mark old token as revoked and link to replacement
            self.repo.revoke_refresh_token(token_model, replaced_by_id=new_token_model.id)

            # Issue new access token
            access_token, expires_in = self.token_service.create_access_token(
                user_id=user.id,
                email=user.email,
                username=user.username,
                system_role=user.system_role,
            )

            self._log_event(
                user_id=user.id,
                event_type=AuthEventType.TOKEN_REFRESH,
                ip=ip_address,
                ua=user_agent,
            )

            return TokenResponse(
                access_token=access_token,
                refresh_token=new_raw_refresh,
                token_type="bearer",
                expires_in=expires_in,
                user=User.model_validate(user),
            )

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Verify current password, update to new Argon2id hash, and revoke all active sessions."""
        user = self.repo.get_user_by_id(user_id)
        if not user or not self.password_service.verify_password(
            current_password, user.hashed_password
        ):
            raise AuthenticationException("Current password verification failed.")
        if len(new_password) < 8:
            raise ValidationException("New password must be at least 8 characters long.")

        user.hashed_password = self.password_service.hash_password(new_password)
        self.repo.update_user(user)

        # Invalidate all active sessions for this user
        revoked_count = self.repo.revoke_all_user_tokens(user.id)
        self._log_event(
            user_id=user.id,
            event_type=AuthEventType.LOGOUT,
            ip=ip_address,
            ua=user_agent,
            details={
                "action": "password_changed_all_sessions_revoked",
                "revoked_count": revoked_count,
            },
        )

    def disable_user(self, user_id: str) -> None:
        """Disable a user account and immediately revoke all active sessions."""
        user = self.repo.get_user_by_id(user_id)
        if user:
            user.is_active = False
            self.repo.update_user(user)
            self.repo.revoke_all_user_tokens(user.id)
            self._log_event(
                user_id=user.id,
                event_type=AuthEventType.ACCESS_DENIED,
                details={"action": "account_disabled_all_sessions_revoked"},
            )

    def logout(
        self,
        raw_refresh_token: str | None,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Invalidate refresh token and record logout audit event."""
        if raw_refresh_token:
            hashed = self.token_service.hash_refresh_token(raw_refresh_token)
            token_model = self.repo.get_refresh_token_by_hash(hashed)
            if token_model:
                self.repo.revoke_refresh_token(token_model)
                user_id = user_id or token_model.user_id

        if user_id:
            self._log_event(
                user_id=user_id,
                event_type=AuthEventType.LOGOUT,
                ip=ip_address,
                ua=user_agent,
            )

    def _log_event(
        self,
        user_id: str | None,
        event_type: AuthEventType,
        username: str | None = None,
        ip: str | None = None,
        ua: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        event = AuthenticationEventModel(
            id=generate_id(),
            user_id=user_id,
            event_type=event_type.value,
            username_attempted=username,
            ip_address=ip,
            user_agent=ua,
            details=details or {},
            created_at=utc_now(),
        )
        self.repo.record_auth_event(event)


class CaseAccessService:
    """Enforces case-scoped Role-Based Access Control (RBAC)."""

    def __init__(self, repo: AuthRepository) -> None:
        self.repo = repo

    def get_user_case_role(self, user: UserModel, case_id: str) -> CaseRole | None:
        """Determine effective role of a user in a given case workspace."""
        # System Admin always has full ADMIN privileges
        if user.system_role == SystemRole.SYSTEM_ADMIN.value:
            return CaseRole.ADMIN

        # Check explicit case membership
        membership = self.repo.get_case_membership(case_id, user.id)
        if membership:
            try:
                return CaseRole(membership.role)
            except ValueError:
                return CaseRole.VIEWER

        # Check organization-level administration
        case = self.repo.get_case(case_id)
        if case and case.organization_id:
            org_member = self.repo.get_org_membership(case.organization_id, user.id)
            if org_member and org_member.role == "ADMIN":
                return CaseRole.ADMIN

        return None

    def check_case_access(
        self,
        user: UserModel,
        case_id: str,
        min_role: CaseRole = CaseRole.VIEWER,
        is_mutation: bool = False,
    ) -> CaseRole:
        """Verify user authorization for a case; raises 404 or 403 upon access failure."""
        case = self.repo.get_case(case_id)
        if not case:
            raise NotFoundException(f"Case '{case_id}' not found.")

        # Check organization isolation if case is assigned to an organization
        if case.organization_id and user.system_role != SystemRole.SYSTEM_ADMIN.value:
            org_member = self.repo.get_org_membership(case.organization_id, user.id)
            # If user has no membership in case's organization, deny access
            if not org_member:
                # Deny by default: 404 to avoid leaking cross-tenant case existence
                raise NotFoundException(f"Case '{case_id}' not found.")

        effective_role = self.get_user_case_role(user, case_id)
        if not effective_role:
            # User is in org but not a member of this specific case workspace
            raise NotFoundException(f"Case '{case_id}' not found in your permitted workspaces.")

        # Check role hierarchy
        has_permission = False
        if min_role == CaseRole.VIEWER:
            has_permission = CaseRole.can_read(effective_role)
        elif min_role == CaseRole.REVIEWER:
            has_permission = CaseRole.can_review(effective_role)
        elif min_role == CaseRole.INVESTIGATOR:
            has_permission = CaseRole.can_mutate(effective_role)
        elif min_role == CaseRole.ADMIN:
            has_permission = CaseRole.can_administer(effective_role)

        if not has_permission:
            raise ForbiddenException(
                f"Action requires role '{min_role.value}', but user holds '{effective_role.value}'."
            )

        # Enforce terminal ARCHIVED state restrictions on mutations
        if is_mutation and case.status == CaseStatus.ARCHIVED.value:
            raise ValidationException(
                f"Cannot execute operations on archived case '{case_id}'. Case is ARCHIVED."
            )

        return effective_role

    def add_case_member(
        self,
        case_id: str,
        target_user_id: str,
        role: CaseRole,
        actor_user: UserModel,
    ) -> CaseMembershipModel:
        """Grant or update case membership (requires Case ADMIN role)."""
        self.check_case_access(actor_user, case_id, min_role=CaseRole.ADMIN, is_mutation=True)

        target_user = self.repo.get_user_by_id(target_user_id)
        if not target_user:
            raise NotFoundException(f"Target user '{target_user_id}' not found.")

        membership = self.repo.add_or_update_case_membership(
            case_id=case_id,
            user_id=target_user_id,
            role=role.value,
            assigned_by=actor_user.id,
        )
        try:
            self.repo.record_auth_event(
                AuthenticationEventModel(
                    id=generate_id(),
                    user_id=actor_user.id,
                    event_type="CASE_MEMBER_ASSIGNED",
                    details={
                        "case_id": case_id,
                        "target_user_id": target_user_id,
                        "role": role.value,
                    },
                    created_at=utc_now(),
                )
            )
        except Exception as exc:
            logger.error("Failed to record case membership audit event: %s", exc)

        return membership

    def remove_case_member(
        self,
        case_id: str,
        target_user_id: str,
        actor_user: UserModel,
    ) -> bool:
        """Revoke user case membership (requires Case ADMIN role)."""
        self.check_case_access(actor_user, case_id, min_role=CaseRole.ADMIN, is_mutation=True)
        res = self.repo.remove_case_membership(case_id, target_user_id)
        try:
            self.repo.record_auth_event(
                AuthenticationEventModel(
                    id=generate_id(),
                    user_id=actor_user.id,
                    event_type="CASE_MEMBER_REMOVED",
                    details={
                        "case_id": case_id,
                        "target_user_id": target_user_id,
                    },
                    created_at=utc_now(),
                )
            )
        except Exception as exc:
            logger.error("Failed to record case member revocation audit event: %s", exc)
        return res
