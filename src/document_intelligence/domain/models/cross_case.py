"""Domain models for explicit cross-case correlation, investigation scoping, and candidate review."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import (
    CrossCaseReviewDecision,
    ResolvedEntityType,
)
from document_intelligence.domain.identifiers import generate_id, utc_now


class CrossCaseScope(BaseModel):
    """An explicit, authorized boundary defining which cases participate in cross-case correlation."""

    id: str = Field(default_factory=generate_id)
    organization_id: str
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    case_ids: list[str] = Field(
        default_factory=list,
        description="Explicit, authorized list of case UUIDs belonging to this investigation scope.",
    )
    created_by: str = Field(description="User ID of the investigator who initialized the scope.")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrossCaseMatchEvidence(BaseModel):
    """Traceable evidence corroborating or conflicting with a cross-case correlation candidate."""

    target_case_id: str
    candidate_case_id: str
    target_mention_id: str
    candidate_mention_id: str
    target_document_id: str
    candidate_document_id: str
    target_page_number: int | None = None
    candidate_page_number: int | None = None
    target_field_key: str
    candidate_field_key: str
    matching_signals: list[str] = Field(default_factory=list)
    contradicting_signals: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    matching_method: str = "deterministic_cross_case_rule"
    match_classification: str = (
        "EXACT_IDENTIFIER"  # EXACT_IDENTIFIER, STRONG_SIMILARITY, WEAK_INDICATOR, CONFLICTING
    )
    coordinates: list[dict[str, Any]] = Field(default_factory=list)


class CrossCaseMatchReview(BaseModel):
    """Immutable audit record of an investigator review decision on a correlation candidate."""

    id: str = Field(default_factory=generate_id)
    match_id: str
    scope_id: str
    decision: CrossCaseReviewDecision
    reviewer_id: str = Field(description="Authenticated user principal ID.")
    reviewer_username: str | None = None
    rationale: str = Field(min_length=1, max_length=1000)
    previous_status: str
    new_status: str
    reviewed_at: datetime = Field(default_factory=utc_now)


class CrossCaseCandidateMatch(BaseModel):
    """An explainable, unmerged correlation candidate linking two entities across different cases."""

    id: str = Field(default_factory=generate_id)
    scope_id: str
    organization_id: str
    entity_type: ResolvedEntityType
    target_case_id: str
    candidate_case_id: str
    target_value_display: str = Field(
        description="Sanitized and PII-masked display representation of the target entity."
    )
    candidate_value_display: str = Field(
        description="Sanitized and PII-masked display representation of the candidate entity."
    )
    raw_target_value_masked: str = Field(
        description="Masked representation of original target value."
    )
    raw_candidate_value_masked: str = Field(
        description="Masked representation of original candidate value."
    )
    matching_method: str = "deterministic_rule"
    match_classification: str = "EXACT_IDENTIFIER"
    match_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Deterministic heuristic confidence score (never a statistical probability).",
    )
    decision_status: CrossCaseReviewDecision = CrossCaseReviewDecision.PENDING_REVIEW
    evidence: CrossCaseMatchEvidence
    review_history: list[CrossCaseMatchReview] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class CrossCaseCorrelationResult(BaseModel):
    """Summary of a bounded correlation analysis pass across an authorized scope."""

    scope_id: str
    organization_id: str
    cases_analyzed: list[str]
    total_mentions_compared: int
    candidate_matches: list[CrossCaseCandidateMatch] = Field(default_factory=list)
    execution_duration_ms: float = 0.0
    executed_at: datetime = Field(default_factory=utc_now)
