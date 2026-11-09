"""Case management API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import get_case_service
from document_intelligence.domain.enums import CaseStatus
from document_intelligence.domain.models.case import Case
from document_intelligence.modules.cases.service import CaseService

router = APIRouter(prefix="/cases", tags=["Cases"])


class CreateCaseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    created_by: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseListResponse(BaseModel):
    items: list[Case]
    total: int
    skip: int
    limit: int


@router.post("", response_model=Case, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CreateCaseRequest,
    case_service: CaseService = Depends(get_case_service),
) -> Case:
    """Create a new forensic investigation case workspace."""
    return case_service.create_case(
        title=payload.title,
        description=payload.description,
        created_by=payload.created_by,
        metadata=payload.metadata,
    )


@router.get("", response_model=CaseListResponse)
async def list_cases(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    case_status: CaseStatus | None = Query(default=None, alias="status"),
    case_service: CaseService = Depends(get_case_service),
) -> CaseListResponse:
    """List investigation cases with pagination."""
    items, total = case_service.list_cases(skip=skip, limit=limit, status=case_status)
    return CaseListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{case_id}", response_model=Case)
async def get_case(
    case_id: str,
    case_service: CaseService = Depends(get_case_service),
) -> Case:
    """Retrieve case by ID."""
    return case_service.get_case(case_id)


@router.post("/{case_id}/archive", response_model=Case)
async def archive_case(
    case_id: str,
    case_service: CaseService = Depends(get_case_service),
) -> Case:
    """Archive an investigation case.

    Case enters terminal ARCHIVED state, preventing new document ingestion or
    analysis execution while preserving complete forensic evidence, processing
    runs, and audit trail ledger records.
    """
    return case_service.archive_case(case_id)
