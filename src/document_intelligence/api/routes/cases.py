"""Case management API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_case_access_service,
    get_case_service,
    get_current_user,
    require_case_access,
)
from document_intelligence.domain.enums import CaseStatus
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.case import Case
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.modules.auth.service import CaseAccessService
from document_intelligence.modules.cases.service import CaseService

router = APIRouter(prefix="/cases", tags=["Cases"])


class CreateCaseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    created_by: str | None = Field(default=None, max_length=100)
    organization_id: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseListResponse(BaseModel):
    items: list[Case]
    total: int
    skip: int
    limit: int


@router.post("", response_model=Case, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CreateCaseRequest,
    current_user: UserModel = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service),
    case_access_service: CaseAccessService = Depends(get_case_access_service),
) -> Case:
    """Create a new forensic investigation case workspace.

    Identity is strictly derived from the authenticated principal. The creator
    is automatically assigned the ADMIN role on the new workspace.
    """
    actor_id = current_user.id
    saved_case = case_service.create_case(
        title=payload.title,
        description=payload.description,
        created_by=actor_id,
        metadata=payload.metadata,
        organization_id=payload.organization_id,
    )

    # Automatically grant ADMIN role to creator
    case_access_service.repo.add_or_update_case_membership(
        case_id=saved_case.id,
        user_id=current_user.id,
        role=CaseRole.ADMIN.value,
        assigned_by=current_user.id,
    )

    return saved_case


@router.get("", response_model=CaseListResponse)
async def list_cases(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    case_status: CaseStatus | None = Query(default=None, alias="status"),
    current_user: UserModel = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service),
    case_access_service: CaseAccessService = Depends(get_case_access_service),
) -> CaseListResponse:
    """List investigation cases with tenant and membership isolation."""
    accessible_ids = case_access_service.repo.list_accessible_case_ids(current_user)
    items, total = case_service.list_cases(
        skip=skip,
        limit=limit,
        status=case_status,
        accessible_case_ids=accessible_ids,
    )
    return CaseListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{case_id}", response_model=Case)
async def get_case(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
) -> Case:
    """Retrieve case by ID with RBAC check."""
    return case_service.get_case(case_id)


@router.post("/{case_id}/archive", response_model=Case)
async def archive_case(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.ADMIN, is_mutation=True)),
    current_user: UserModel = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service),
) -> Case:
    """Archive an investigation case.

    Case enters terminal ARCHIVED state, preventing new document ingestion or
    analysis execution while preserving complete forensic evidence, processing
    runs, and audit trail ledger records. Requires ADMIN role.
    """
    return case_service.archive_case(case_id, actor_id=current_user.id)
