"""Forensic findings query endpoints."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from document_intelligence.api.dependencies import (
    get_case_service,
    get_finding_repository,
    require_case_access,
)
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.infrastructure.repositories.finding_repository import (
    FindingRepository,
)
from document_intelligence.modules.cases.service import CaseService

router = APIRouter(prefix="/cases/{case_id}/findings", tags=["Findings"])


class FindingListResponse(BaseModel):
    items: list[ForensicFinding]
    total: int
    skip: int
    limit: int


@router.get("", response_model=FindingListResponse)
async def list_findings(
    case_id: str,
    document_id: str | None = Query(default=None, description="Filter by document ID"),
    processing_run_id: str | None = Query(default=None, description="Filter by processing run ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
    finding_repo: FindingRepository = Depends(get_finding_repository),
) -> FindingListResponse:
    """Retrieve detected forensic findings for a case with optional document or run filter."""
    # Verify case exists
    case_service.get_case(case_id)

    items, total = finding_repo.list_by_case(
        case_id=case_id,
        document_id=document_id,
        processing_run_id=processing_run_id,
        skip=skip,
        limit=limit,
    )
    return FindingListResponse(items=items, total=total, skip=skip, limit=limit)
