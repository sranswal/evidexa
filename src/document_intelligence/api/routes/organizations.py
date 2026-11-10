"""Organization and Multi-Tenant Security REST API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_auth_repo,
    get_case_service,
    get_current_user,
)
from document_intelligence.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from document_intelligence.domain.models.auth import Organization
from document_intelligence.domain.models.case import Case
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.infrastructure.repositories.auth_repository import AuthRepository
from document_intelligence.modules.cases.service import CaseService

router = APIRouter(prefix="/organizations", tags=["Organizations & Multi-Tenancy"])


class AddOrgMemberRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = Field(default="MEMBER")


class OrgMemberResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    role: str
    username: str
    email: str


@router.get("/{org_id}", response_model=Organization, status_code=status.HTTP_200_OK)
def get_organization(
    org_id: str,
    current_user: UserModel = Depends(get_current_user),
    auth_repo: AuthRepository = Depends(get_auth_repo),
) -> Organization:
    """Retrieve organization details enforcing tenant membership boundaries."""
    org = auth_repo.get_organization_by_id(org_id)
    if not org:
        raise NotFoundException(f"Organization '{org_id}' not found.")

    if current_user.system_role != "SYSTEM_ADMIN":
        membership = auth_repo.get_org_membership(org_id, current_user.id)
        if not membership:
            raise ForbiddenException(f"User is not a member of organization '{org_id}'.")

    return Organization.model_validate(org)


@router.post(
    "/{org_id}/members",
    response_model=OrgMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_organization_member(
    org_id: str,
    payload: AddOrgMemberRequest,
    current_user: UserModel = Depends(get_current_user),
    auth_repo: AuthRepository = Depends(get_auth_repo),
) -> OrgMemberResponse:
    """Add or update an organization member (Requires Organization ADMIN role)."""
    org = auth_repo.get_organization_by_id(org_id)
    if not org:
        raise NotFoundException(f"Organization '{org_id}' not found.")

    if current_user.system_role != "SYSTEM_ADMIN":
        membership = auth_repo.get_org_membership(org_id, current_user.id)
        if not membership or membership.role != "ADMIN":
            raise ForbiddenException(
                "Only organization administrators can manage organization membership."
            )

    target_user = auth_repo.get_user_by_id(payload.user_id)
    if not target_user:
        raise NotFoundException(f"Target user '{payload.user_id}' not found.")

    valid_roles = {"ADMIN", "MEMBER"}
    if payload.role.upper() not in valid_roles:
        raise ValidationException(
            f"Invalid organization role '{payload.role}'. Must be one of: {valid_roles}"
        )

    member = auth_repo.add_org_membership(org_id, target_user.id, role=payload.role.upper())
    return OrgMemberResponse(
        id=member.id,
        organization_id=member.organization_id,
        user_id=target_user.id,
        role=member.role,
        username=target_user.username,
        email=target_user.email,
    )


@router.get(
    "/{org_id}/cases",
    response_model=list[Case],
    status_code=status.HTTP_200_OK,
)
def list_organization_cases(
    org_id: str,
    current_user: UserModel = Depends(get_current_user),
    auth_repo: AuthRepository = Depends(get_auth_repo),
    case_service: CaseService = Depends(get_case_service),
) -> list[Case]:
    """List investigation cases scoped strictly to an organization tenant."""
    org = auth_repo.get_organization_by_id(org_id)
    if not org:
        raise NotFoundException(f"Organization '{org_id}' not found.")

    if current_user.system_role != "SYSTEM_ADMIN":
        membership = auth_repo.get_org_membership(org_id, current_user.id)
        if not membership:
            raise ForbiddenException(
                f"User is not authorized to access cases in organization '{org_id}'."
            )

    # List all cases belonging to org_id
    from sqlalchemy import select

    from document_intelligence.infrastructure.persistence.models import CaseModel

    stmt = (
        select(CaseModel)
        .where(CaseModel.organization_id == org_id)
        .order_by(CaseModel.created_at.desc())
    )
    models = auth_repo.db.scalars(stmt).all()
    return [case_service.case_repo._to_domain(m) for m in models]
