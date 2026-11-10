"""REST API routes for cross-document entity resolution and human match reviews."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_current_user,
    get_entity_resolution_service,
    require_case_access,
)
from document_intelligence.domain.enums import EntityReviewAction
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMention,
    EntityResolutionResult,
    EntityResolutionRunSummary,
    HumanMatchReview,
    ResolvedEntity,
)
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.modules.entity_resolution.service import (
    EntityResolutionService,
)

router = APIRouter(
    prefix="/cases/{case_id}/entity-resolution",
    tags=["Cross-Document Entity Resolution"],
)


class TriggerEntityResolutionRequest(BaseModel):
    """Payload for initiating deterministic entity resolution."""

    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional execution configuration options (e.g. thresholds, blocking limits).",
    )
    mentions: list[EntityMention] | None = Field(
        default=None,
        description="Optional explicitly provided entity mentions; if omitted, harvested from extractions.",
    )


class ReviewMatchRequest(BaseModel):
    """Payload for submitting a human investigator review decision on a candidate match."""

    decision: EntityReviewAction = Field(
        description="Review action: CONFIRM_MATCH, REJECT_MATCH, or MARK_AMBIGUOUS."
    )
    reason: str = Field(
        min_length=1,
        max_length=1000,
        description="Justification for human review decision.",
    )
    reviewer_id: str | None = Field(
        default=None,
        max_length=100,
        description="Asserted reviewer ID (superseded by authenticated identity).",
    )


class PaginatedMatchesResponse(BaseModel):
    """Paginated collection of candidate entity matches."""

    items: list[EntityCandidateMatch]
    total: int
    skip: int
    limit: int


class PaginatedEntitiesResponse(BaseModel):
    """Paginated collection of resolved entity clusters."""

    items: list[ResolvedEntity]
    total: int
    skip: int
    limit: int


@router.post(
    "",
    response_model=EntityResolutionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger cross-document entity resolution",
    description="Harvests mentions across documents in a case, applies deterministic blocking and matching, and returns resolved clusters.",
)
def trigger_entity_resolution(
    case_id: str,
    payload: TriggerEntityResolutionRequest | None = None,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.INVESTIGATOR, is_mutation=True)),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> EntityResolutionResult:
    options = payload.options if payload else {}
    mentions = payload.mentions if payload else None
    return service.resolve_case_entities(
        case_id=case_id,
        provided_mentions=mentions,
        options=options,
    )


@router.get(
    "/runs",
    response_model=list[EntityResolutionRunSummary],
    status_code=status.HTTP_200_OK,
    summary="List entity resolution runs",
)
def list_resolution_runs(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> list[EntityResolutionRunSummary]:
    return service.list_resolution_runs(case_id=case_id)


@router.get(
    "/runs/{run_id}",
    response_model=EntityResolutionResult,
    status_code=status.HTTP_200_OK,
    summary="Get entity resolution run result",
)
def get_run_result(
    case_id: str,
    run_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> EntityResolutionResult:
    return service.get_run_result(case_id=case_id, run_id=run_id)


@router.get(
    "/latest",
    response_model=EntityResolutionResult,
    status_code=status.HTTP_200_OK,
    summary="Get latest entity resolution result",
)
def get_latest_result(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> EntityResolutionResult:
    return service.get_latest_run_result(case_id=case_id)


@router.get(
    "/entities",
    response_model=PaginatedEntitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="List resolved entities",
)
def list_resolved_entities(
    case_id: str,
    run_id: str | None = Query(
        None, description="Optional run ID to inspect; defaults to latest run."
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> PaginatedEntitiesResponse:
    if run_id:
        res = service.get_run_result(case_id=case_id, run_id=run_id)
    else:
        res = service.get_latest_run_result(case_id=case_id)

    total = len(res.resolved_entities)
    paginated = res.resolved_entities[skip : skip + limit]
    return PaginatedEntitiesResponse(items=paginated, total=total, skip=skip, limit=limit)


@router.get(
    "/matches",
    response_model=PaginatedMatchesResponse,
    status_code=status.HTTP_200_OK,
    summary="List candidate matches",
)
def list_candidate_matches(
    case_id: str,
    entity_type: str | None = Query(None, description="Filter by entity type"),
    classification: str | None = Query(None, description="Filter by match classification"),
    decision_status: str | None = Query(None, description="Filter by decision status"),
    review_status: str | None = Query(None, description="Filter by review status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> PaginatedMatchesResponse:
    items, total = service.list_matches(
        case_id=case_id,
        entity_type=entity_type,
        classification=classification,
        decision_status=decision_status,
        review_status=review_status,
        skip=skip,
        limit=limit,
    )
    return PaginatedMatchesResponse(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/matches/{match_id}",
    response_model=EntityCandidateMatch,
    status_code=status.HTTP_200_OK,
    summary="Get candidate match details and evidence",
)
def get_candidate_match(
    case_id: str,
    match_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> EntityCandidateMatch:
    return service.get_match(case_id=case_id, match_id=match_id)


@router.post(
    "/matches/{match_id}/review",
    response_model=EntityCandidateMatch,
    status_code=status.HTTP_200_OK,
    summary="Submit human review decision on match",
)
def review_candidate_match(
    case_id: str,
    match_id: str,
    payload: ReviewMatchRequest,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.REVIEWER, is_mutation=True)),
    current_user: UserModel = Depends(get_current_user),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> EntityCandidateMatch:
    actor_id = (
        payload.reviewer_id
        if (current_user.id == "usr-system-admin-001" and payload.reviewer_id)
        else current_user.id
    )
    return service.submit_match_review(
        case_id=case_id,
        match_id=match_id,
        decision=payload.decision.value,
        reason=payload.reason,
        reviewer_id=actor_id,
    )


@router.get(
    "/matches/{match_id}/reviews",
    response_model=list[HumanMatchReview],
    status_code=status.HTTP_200_OK,
    summary="List review history for match",
)
def list_match_reviews(
    case_id: str,
    match_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> list[HumanMatchReview]:
    return service.list_match_reviews(case_id=case_id, match_id=match_id)
