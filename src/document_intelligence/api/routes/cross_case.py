"""API routes for Cross-Case Investigation Scopes, Correlation Intelligence, and Reviews."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_cross_case_service,
    get_current_user,
)
from document_intelligence.domain.enums import CrossCaseReviewDecision
from document_intelligence.domain.models.cross_case import (
    CrossCaseCandidateMatch,
    CrossCaseCorrelationResult,
    CrossCaseScope,
)
from document_intelligence.domain.models.graph import GraphSnapshot
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.modules.cross_case.service import CrossCaseCorrelationService

router = APIRouter(prefix="/cross-case", tags=["Cross-Case Intelligence"])


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------


class CreateScopeRequest(BaseModel):
    name: str = Field(
        min_length=1, max_length=200, description="Title of the cross-case investigation."
    )
    case_ids: list[str] = Field(
        min_length=1, description="List of authorized case IDs to correlate."
    )
    description: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateScopeCasesRequest(BaseModel):
    case_ids: list[str] = Field(min_length=1, description="Updated list of authorized case IDs.")


class ReviewCandidateRequest(BaseModel):
    decision: CrossCaseReviewDecision = Field(
        description="Review action: ACCEPTED, REJECTED, or NEEDS_FURTHER_INVESTIGATION."
    )
    rationale: str = Field(
        min_length=1, max_length=1000, description="Investigator review rationale."
    )


class PaginatedCandidatesResponse(BaseModel):
    items: list[CrossCaseCandidateMatch]
    total: int
    limit: int
    offset: int


# -----------------------------------------------------------------------------
# Investigation Scope Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/scopes",
    response_model=CrossCaseScope,
    status_code=status.HTTP_201_CREATED,
    summary="Create an explicit cross-case investigation scope",
)
def create_scope(
    request: CreateScopeRequest,
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> CrossCaseScope:
    """Create a new bounded cross-case investigation scope verifying case permissions."""
    return service.create_scope(
        name=request.name,
        case_ids=request.case_ids,
        description=request.description,
        metadata=request.metadata,
        user=current_user,
    )


@router.get(
    "/scopes",
    response_model=list[CrossCaseScope],
    status_code=status.HTTP_200_OK,
    summary="List cross-case investigation scopes",
)
def list_scopes(
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> list[CrossCaseScope]:
    """Retrieve all accessible cross-case scopes for the authenticated user's organization."""
    return service.list_scopes(user=current_user)


@router.get(
    "/scopes/{scope_id}",
    response_model=CrossCaseScope,
    status_code=status.HTTP_200_OK,
    summary="Retrieve cross-case investigation scope",
)
def get_scope(
    scope_id: str,
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> CrossCaseScope:
    """Retrieve an investigation scope with runtime revalidation of case access."""
    return service.get_scope(scope_id=scope_id, user=current_user)


@router.put(
    "/scopes/{scope_id}/cases",
    response_model=CrossCaseScope,
    status_code=status.HTTP_200_OK,
    summary="Update cases in an investigation scope",
)
def update_scope_cases(
    scope_id: str,
    request: UpdateScopeCasesRequest,
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> CrossCaseScope:
    """Add or remove cases from an existing investigation scope."""
    return service.update_scope_cases(
        scope_id=scope_id, case_ids=request.case_ids, user=current_user
    )


# -----------------------------------------------------------------------------
# Correlation Execution & Candidate Matches
# -----------------------------------------------------------------------------


@router.post(
    "/scopes/{scope_id}/correlate",
    response_model=CrossCaseCorrelationResult,
    status_code=status.HTTP_200_OK,
    summary="Execute cross-case correlation analysis",
)
def execute_correlation(
    scope_id: str,
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> CrossCaseCorrelationResult:
    """Trigger bounded deterministic correlation across cases in the authorized scope."""
    return service.run_correlation(scope_id=scope_id, user=current_user)


@router.get(
    "/scopes/{scope_id}/candidates",
    response_model=PaginatedCandidatesResponse,
    status_code=status.HTTP_200_OK,
    summary="List correlation candidates for an investigation scope",
)
def list_candidates(
    scope_id: str,
    decision_status: str | None = Query(
        None, description="Filter by decision status (PENDING_REVIEW, ACCEPTED, etc.)"
    ),
    entity_type: str | None = Query(
        None, description="Filter by entity type (ORGANIZATION, PERSON, etc.)"
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> PaginatedCandidatesResponse:
    """Retrieve paginated correlation candidate matches with evidentiary signals."""
    items, total = service.list_candidates(
        scope_id=scope_id,
        user=current_user,
        decision_status=decision_status,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return PaginatedCandidatesResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/scopes/{scope_id}/candidates/{match_id}",
    response_model=CrossCaseCandidateMatch,
    status_code=status.HTTP_200_OK,
    summary="Retrieve candidate match details",
)
def get_candidate(
    scope_id: str,
    match_id: str,
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> CrossCaseCandidateMatch:
    """Inspect full evidentiary details and review history of a correlation candidate."""
    return service.get_candidate(scope_id=scope_id, match_id=match_id, user=current_user)


@router.post(
    "/scopes/{scope_id}/candidates/{match_id}/review",
    response_model=CrossCaseCandidateMatch,
    status_code=status.HTTP_200_OK,
    summary="Submit investigator review decision",
)
def review_candidate(
    scope_id: str,
    match_id: str,
    request: ReviewCandidateRequest,
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> CrossCaseCandidateMatch:
    """Record an investigator review decision (ACCEPTED, REJECTED, NEEDS_FURTHER_INVESTIGATION)."""
    return service.review_candidate(
        scope_id=scope_id,
        match_id=match_id,
        decision=request.decision,
        rationale=request.rationale,
        user=current_user,
    )


# -----------------------------------------------------------------------------
# Cross-Case Evidence Graph
# -----------------------------------------------------------------------------


@router.get(
    "/scopes/{scope_id}/graph",
    response_model=GraphSnapshot,
    status_code=status.HTTP_200_OK,
    summary="Query multi-case Evidence Graph with correlation overlay",
)
def get_cross_case_graph(
    scope_id: str,
    max_hops: int = Query(default=2, ge=1, le=5),
    max_nodes: int = Query(default=500, ge=10, le=1000),
    current_user: UserModel = Depends(get_current_user),
    service: CrossCaseCorrelationService = Depends(get_cross_case_service),
) -> GraphSnapshot:
    """Project unified Evidence Graph spanning all authorized cases in the scope."""
    return service.get_cross_case_graph(
        scope_id=scope_id, user=current_user, max_hops=max_hops, max_nodes=max_nodes
    )
