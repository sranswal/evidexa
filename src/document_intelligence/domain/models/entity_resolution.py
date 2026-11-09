"""Domain models for cross-document deterministic entity resolution and evidence tracking."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import (
    EntityMatchClassification,
    EntityMatchingMethod,
    EntityReviewAction,
    HumanReviewStatus,
    MatchDecisionStatus,
    ResolvedEntityType,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.bounding_box import BoundingBox


class EntityMention(BaseModel):
    """An atomic real-world entity mention extracted from a document with full provenance."""

    mention_id: str = Field(default_factory=generate_id)
    case_id: str
    document_id: str
    page_number: int = Field(ge=1)
    processing_run_id: str
    field_key: str
    entity_type: ResolvedEntityType
    original_value: str = Field(
        description="Original extracted text, strictly sanitized to adhere to PII rules."
    )
    normalized_value: str = Field(
        description="Safe canonical normalized value for deterministic comparison."
    )
    numeric_amount: Decimal | None = None
    currency_code: str | None = None
    jurisdiction: str | None = None
    identifier_type: str | None = None
    legal_suffix: str | None = None
    base_name: str | None = None
    supporting_evidence_node_ids: list[str] = Field(default_factory=list)
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)
    extraction_method: str = "deterministic_field_extraction"
    schema_version: str = "1.0.0"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityMatchEvidence(BaseModel):
    """Traceable supporting and contradicting evidentiary signals connecting candidate mentions."""

    target_mention_id: str
    candidate_mention_id: str
    target_document_id: str
    candidate_document_id: str
    target_page_number: int
    candidate_page_number: int
    target_field_key: str
    candidate_field_key: str
    target_evidence_node_ids: list[str] = Field(default_factory=list)
    candidate_evidence_node_ids: list[str] = Field(default_factory=list)
    matching_signals: list[str] = Field(default_factory=list)
    contradicting_signals: list[str] = Field(default_factory=list)
    resolution_algorithm_version: str = "1.0.0"


class HumanMatchReview(BaseModel):
    """Human investigator review record preserving decision history without erasing evidence."""

    id: str = Field(default_factory=generate_id)
    match_id: str
    case_id: str
    decision: EntityReviewAction
    reviewer_id: str = Field(
        description="Asserted reviewer identifier in unauthenticated development mode."
    )
    reason: str = Field(min_length=1, max_length=1000)
    reviewed_at: datetime = Field(default_factory=utc_now)
    previous_status: MatchDecisionStatus
    new_status: MatchDecisionStatus


class EntityCandidateMatch(BaseModel):
    """Evaluated match between two entity mentions with explicit uncertainty and evidence."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    processing_run_id: str
    entity_type: ResolvedEntityType
    target_mention_id: str
    candidate_mention_id: str
    target_value_display: str
    candidate_value_display: str
    matching_method: EntityMatchingMethod
    match_classification: EntityMatchClassification
    match_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Deterministic similarity or rule score. Explicitly uncalibrated; NOT a probability.",
    )
    score_semantics: str = Field(
        default="deterministic_rule_score",
        description="Transparent explanation of score meaning and bounds.",
    )
    decision_status: MatchDecisionStatus = MatchDecisionStatus.ALGORITHMIC_CANDIDATE
    review_status: HumanReviewStatus = HumanReviewStatus.UNREVIEWED
    evidence: EntityMatchEvidence
    review_history: list[HumanMatchReview] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ResolvedEntity(BaseModel):
    """An identity cluster grouping mentions evaluated or confirmed as representing the same entity."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    entity_type: ResolvedEntityType
    canonical_name: str
    mention_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    is_confirmed: bool = False
    candidate_match_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityResolutionResult(BaseModel):
    """Comprehensive, self-contained result of an entity resolution pass over a case."""

    case_id: str
    processing_run_id: str
    total_mentions: int
    total_comparisons: int
    candidate_matches: list[EntityCandidateMatch] = Field(default_factory=list)
    resolved_entities: list[ResolvedEntity] = Field(default_factory=list)
    unresolved_mentions: list[EntityMention] = Field(default_factory=list)
    blocking_summary: dict[str, int] = Field(default_factory=dict)
    execution_duration_ms: float = 0.0
    algorithm_version: str = "1.0.0"
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None
    evaluated_at: datetime = Field(default_factory=utc_now)


class EntityResolutionRunSummary(BaseModel):
    """Summary record of an entity resolution execution run."""

    run_id: str
    case_id: str
    pipeline_name: str
    pipeline_version: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    total_mentions: int = 0
    total_matches: int = 0
    total_entities: int = 0
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None
