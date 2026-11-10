"""REST API routes for cross-document consistency analysis and human reviewer decisions."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_consistency_service,
    get_current_user,
    require_case_access,
)
from document_intelligence.domain.enums import ConsistencyReviewAction
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.consistency import (
    ConsistencyAnalysisResult,
    ConsistencyFinding,
    ConsistencyReview,
)
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.modules.consistency.service import (
    ConsistencyAnalysisService,
)

router = APIRouter(
    prefix="/cases/{case_id}/consistency",
    tags=["Cross-Document Consistency Engine"],
)


class ConsistencyAnalyzeRequest(BaseModel):
    """Payload for triggering cross-document consistency analysis."""

    document_ids: list[str] | None = Field(
        default=None,
        description="Optional subset of document IDs within the case to analyze. Defaults to all case documents.",
    )
    rule_ids: list[str] | None = Field(
        default=None,
        description="Optional subset of rule IDs to evaluate. Defaults to all registered consistency rules.",
    )
    monetary_tolerance: Decimal | None = Field(
        default=None,
        ge=Decimal("0.00"),
        description="Configurable tolerance for monetary comparisons (e.g. 0.00 for exact match).",
    )
    parameters: dict[str, Any] | None = Field(
        default=None,
        description="Optional rule configuration or synthetic transaction parameters.",
    )


class ConsistencyReviewRequest(BaseModel):
    """Payload for recording a human review decision on a consistency finding."""

    decision: ConsistencyReviewAction = Field(
        description="Action: CONFIRM_INCONSISTENCY, DISMISS, MARK_INSUFFICIENT_EVIDENCE, or REQUEST_MORE_EVIDENCE."
    )
    reviewer_id: str | None = Field(
        default=None,
        max_length=100,
        description="Asserted reviewer or investigator identifier (superseded by authenticated identity).",
    )
    reason: str = Field(
        min_length=1,
        max_length=1000,
        description="Mandatory factual justification for the review decision.",
    )


class PaginatedConsistencyFindingsResponse(BaseModel):
    """Paginated collection of consistency findings."""

    findings: list[ConsistencyFinding]
    total: int
    limit: int
    offset: int


@router.post(
    "/analyze",
    response_model=ConsistencyAnalysisResult,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger cross-document consistency analysis",
)
def analyze_case_consistency(
    case_id: str,
    request: ConsistencyAnalyzeRequest | None = None,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.INVESTIGATOR, is_mutation=True)),
    service: ConsistencyAnalysisService = Depends(get_consistency_service),
) -> ConsistencyAnalysisResult:
    """Execute deterministic consistency rules across documents belonging to the same case."""
    req = request or ConsistencyAnalyzeRequest()
    return service.analyze_case(
        case_id=case_id,
        document_ids=req.document_ids,
        rule_ids=req.rule_ids,
        monetary_tolerance=req.monetary_tolerance,
        parameters=req.parameters,
    )


@router.get(
    "/runs",
    response_model=list[ProcessingRun],
    summary="List consistency analysis runs for a case",
)
def list_consistency_runs(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: ConsistencyAnalysisService = Depends(get_consistency_service),
) -> list[ProcessingRun]:
    """Retrieve historical consistency analysis runs for the specified case."""
    return service.get_runs_for_case(case_id=case_id)


@router.get(
    "/runs/{run_id}",
    response_model=ProcessingRun,
    summary="Retrieve a specific consistency analysis run",
)
def get_consistency_run(
    case_id: str,
    run_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: ConsistencyAnalysisService = Depends(get_consistency_service),
) -> ProcessingRun:
    """Retrieve execution metadata for an individual consistency analysis run."""
    return service.get_run(case_id=case_id, run_id=run_id)


@router.get(
    "/findings",
    response_model=PaginatedConsistencyFindingsResponse,
    summary="List consistency findings with filtering",
)
def list_consistency_findings(
    case_id: str,
    run_id: str | None = Query(None, description="Filter by analysis run ID"),
    rule_id: str | None = Query(None, description="Filter by consistency rule ID"),
    outcome: str | None = Query(
        None, description="Filter by outcome: CONSISTENT, INCONSISTENT, etc."
    ),
    status: str | None = Query(None, description="Filter by investigation status"),
    document_id: str | None = Query(None, description="Filter by affected document ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: ConsistencyAnalysisService = Depends(get_consistency_service),
) -> PaginatedConsistencyFindingsResponse:
    """List cross-document consistency findings with case isolation and flexible filtering."""
    findings = service.list_findings(
        case_id=case_id,
        run_id=run_id,
        rule_id=rule_id,
        outcome=outcome,
        status=status,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )
    total = service.consistency_repo.count_findings(
        case_id=case_id,
        run_id=run_id,
        rule_id=rule_id,
        outcome=outcome,
        status=status,
    )
    return PaginatedConsistencyFindingsResponse(
        findings=findings,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/findings/{finding_id}",
    response_model=ConsistencyFinding,
    summary="Retrieve an individual consistency finding",
)
def get_consistency_finding(
    case_id: str,
    finding_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: ConsistencyAnalysisService = Depends(get_consistency_service),
) -> ConsistencyFinding:
    """Retrieve details, compared fields, and evidentiary locations for a specific finding."""
    return service.get_finding_or_404(case_id=case_id, finding_id=finding_id)


@router.post(
    "/findings/{finding_id}/reviews",
    response_model=ConsistencyFinding,
    status_code=status.HTTP_201_CREATED,
    summary="Submit human review decision on a consistency finding",
)
def review_consistency_finding(
    case_id: str,
    finding_id: str,
    request: ConsistencyReviewRequest,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.REVIEWER, is_mutation=True)),
    current_user: UserModel = Depends(get_current_user),
    service: ConsistencyAnalysisService = Depends(get_consistency_service),
) -> ConsistencyFinding:
    """Apply an investigator review decision to a consistency finding, recording an append-only audit event."""
    actor_id = (
        request.reviewer_id
        if (current_user.id == "usr-system-admin-001" and request.reviewer_id)
        else current_user.id
    )
    return service.review_finding(
        case_id=case_id,
        finding_id=finding_id,
        decision=request.decision,
        reviewer_id=actor_id,
        reason=request.reason,
    )


@router.get(
    "/findings/{finding_id}/reviews",
    response_model=list[ConsistencyReview],
    summary="Retrieve human review history for a finding",
)
def get_consistency_review_history(
    case_id: str,
    finding_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: ConsistencyAnalysisService = Depends(get_consistency_service),
) -> list[ConsistencyReview]:
    """Retrieve chronological review decisions and justifications for a consistency finding."""
    return service.get_review_history(case_id=case_id, finding_id=finding_id)
