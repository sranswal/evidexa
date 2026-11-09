"""REST API routes for cross-document relationship discovery and human reviews."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import get_relationship_service
from document_intelligence.domain.enums import RelationshipReviewAction
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipDetectionResult,
    RelationshipDetectionRun,
    RelationshipReviewRecord,
)
from document_intelligence.modules.relationship_detection.service import (
    RelationshipDetectionService,
)

router = APIRouter(
    prefix="/cases/{case_id}/relationships",
    tags=["Cross-Document Relationship Engine"],
)


class TriggerRelationshipDetectionRequest(BaseModel):
    """Payload for initiating deterministic relationship detection."""

    synthetic_transactions: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional synthetic bank transactions for settlement evaluation.",
    )
    caller_id: str | None = Field(
        default=None,
        description="Asserted identifier of the calling investigator or service.",
    )


class ReviewRelationshipRequest(BaseModel):
    """Payload for submitting a human investigator review decision on a relationship."""

    decision: RelationshipReviewAction = Field(
        description="Review action: CONFIRM_RELATIONSHIP, REJECT_RELATIONSHIP, or MARK_UNRESOLVED."
    )
    reason: str = Field(
        min_length=1,
        max_length=1000,
        description="Justification for human review decision.",
    )
    reviewer_id: str = Field(
        min_length=1,
        max_length=100,
        description="Asserted reviewer or investigator identifier (unauthenticated in development mode).",
    )


class PaginatedRelationshipsResponse(BaseModel):
    """Paginated collection of detected relationships."""

    ontology_version: str = "2.0"
    items: list[DetectedRelationship]
    total: int
    skip: int
    limit: int


@router.post(
    "",
    response_model=RelationshipDetectionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger cross-document relationship detection",
    description="Harvests extracted fields, document metadata, and entity matches to identify evidence-backed relationships.",
)
def trigger_relationship_detection(
    case_id: str,
    payload: TriggerRelationshipDetectionRequest | None = None,
    service: RelationshipDetectionService = Depends(get_relationship_service),
) -> RelationshipDetectionResult:
    synthetic_txs = payload.synthetic_transactions if payload else None
    caller_id = payload.caller_id if payload else None
    return service.detect_relationships_for_case(
        case_id=case_id,
        synthetic_transactions=synthetic_txs,
        caller_id=caller_id,
    )


@router.get(
    "/runs",
    response_model=list[RelationshipDetectionRun],
    status_code=status.HTTP_200_OK,
    summary="List relationship detection runs",
)
def list_detection_runs(
    case_id: str,
    service: RelationshipDetectionService = Depends(get_relationship_service),
) -> list[RelationshipDetectionRun]:
    return service.list_runs(case_id=case_id)


@router.get(
    "/runs/{run_id}",
    response_model=RelationshipDetectionResult,
    status_code=status.HTTP_200_OK,
    summary="Get relationship detection run result",
)
def get_run_result(
    case_id: str,
    run_id: str,
    service: RelationshipDetectionService = Depends(get_relationship_service),
) -> RelationshipDetectionResult:
    return service.get_run_result(case_id=case_id, run_id=run_id)


@router.get(
    "/latest",
    response_model=RelationshipDetectionResult,
    status_code=status.HTTP_200_OK,
    summary="Get latest relationship detection result",
)
def get_latest_result(
    case_id: str,
    service: RelationshipDetectionService = Depends(get_relationship_service),
) -> RelationshipDetectionResult:
    return service.get_latest_result(case_id=case_id)


@router.get(
    "",
    response_model=PaginatedRelationshipsResponse,
    status_code=status.HTTP_200_OK,
    summary="List detected relationships",
)
def list_detected_relationships(
    case_id: str,
    relationship_type: str | None = Query(None, description="Filter by relationship type"),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by relationship status"
    ),
    source_id: str | None = Query(None, description="Filter by source ID"),
    target_id: str | None = Query(None, description="Filter by target ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: RelationshipDetectionService = Depends(get_relationship_service),
) -> PaginatedRelationshipsResponse:
    items, total = service.list_relationships(
        case_id=case_id,
        relationship_type=relationship_type,
        status=status_filter,
        source_id=source_id,
        target_id=target_id,
        skip=skip,
        limit=limit,
    )
    return PaginatedRelationshipsResponse(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{relationship_id}",
    response_model=DetectedRelationship,
    status_code=status.HTTP_200_OK,
    summary="Get relationship details and evidence",
)
def get_relationship(
    case_id: str,
    relationship_id: str,
    service: RelationshipDetectionService = Depends(get_relationship_service),
) -> DetectedRelationship:
    return service.get_relationship(case_id=case_id, relationship_id=relationship_id)


@router.post(
    "/{relationship_id}/review",
    response_model=DetectedRelationship,
    status_code=status.HTTP_200_OK,
    summary="Submit human review decision on relationship",
)
def review_relationship(
    case_id: str,
    relationship_id: str,
    payload: ReviewRelationshipRequest,
    service: RelationshipDetectionService = Depends(get_relationship_service),
) -> DetectedRelationship:
    return service.review_relationship(
        case_id=case_id,
        relationship_id=relationship_id,
        decision=payload.decision,
        reviewer_id=payload.reviewer_id,
        reason=payload.reason,
    )


@router.get(
    "/{relationship_id}/reviews",
    response_model=list[RelationshipReviewRecord],
    status_code=status.HTTP_200_OK,
    summary="List review history for relationship",
)
def list_relationship_reviews(
    case_id: str,
    relationship_id: str,
    service: RelationshipDetectionService = Depends(get_relationship_service),
) -> list[RelationshipReviewRecord]:
    return service.list_relationship_reviews(case_id=case_id, relationship_id=relationship_id)
