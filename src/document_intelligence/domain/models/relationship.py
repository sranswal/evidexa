"""Domain models for cross-document deterministic relationship detection and evidence tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import (
    DuplicateKind,
    RelationshipDetectionMethod,
    RelationshipReviewAction,
    RelationshipStatus,
    RelationshipType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.bounding_box import BoundingBox


class RelationshipMention(BaseModel):
    """An atomic mention or node reference participating in a detected relationship."""

    mention_id: str = Field(default_factory=generate_id)
    case_id: str
    document_id: str
    page_number: int | None = Field(default=None, ge=1)
    field_key: str | None = None
    node_type: str = Field(
        description="Type of entity/document node (e.g. DOCUMENT, ORGANIZATION, PERSON, TRANSACTION, INVOICE)."
    )
    label: str = Field(description="Display label or sanitized value for the mention.")
    evidence_node_ids: list[str] = Field(default_factory=list)
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationshipEvidence(BaseModel):
    """Traceable supporting and contradicting evidentiary signals connecting related records."""

    relationship_type: RelationshipType
    ontology_version: str = "2.0"
    legacy_relationship_type: str | None = None
    source_id: str
    target_id: str
    source_case_id: str
    source_extraction_run_id: str | None = None
    source_field_keys: list[str] = Field(default_factory=list)
    supporting_evidence_node_ids: list[str] = Field(default_factory=list)
    source_page_references: list[int] = Field(default_factory=list)
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)
    detection_method: RelationshipDetectionMethod = (
        RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE
    )
    detection_version: str = "2.0.0"
    duplicate_kind: DuplicateKind | None = None
    matching_signals: list[str] = Field(default_factory=list)
    contradicting_signals: list[str] = Field(default_factory=list)
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Deterministic heuristic strength or rule ranking score. Never calibrated probability.",
    )
    score_semantics: str = Field(
        description="Explicit description of the score (e.g. 'rule_ranking_score', 'evidence_strength', 'similarity_score')."
    )
    status: RelationshipStatus
    status_determination_method: StatusDeterminationMethod = (
        StatusDeterminationMethod.EVIDENTIARY_RULE
    )
    status_rationale: str = Field(
        description="Detailed factual rationale explaining why this status and classification was assigned."
    )
    review_history_references: list[str] = Field(default_factory=list)


class RelationshipReviewRecord(BaseModel):
    """Human investigator review record preserving decision history without erasing algorithmic evidence."""

    id: str = Field(default_factory=generate_id)
    relationship_id: str
    case_id: str
    decision: RelationshipReviewAction
    reviewer_id: str = Field(description="Asserted reviewer identifier in development mode.")
    reason: str = Field(min_length=1, max_length=1000)
    reviewed_at: datetime = Field(default_factory=utc_now)
    previous_status: RelationshipStatus
    new_status: RelationshipStatus


class DetectedRelationship(BaseModel):
    """A detected, evidence-backed relationship connecting entities, documents, or financial records."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    detection_run_id: str
    relationship_type: RelationshipType
    ontology_version: str = "2.0"
    legacy_relationship_type: str | None = None
    source_id: str = Field(description="Source entity ID, document ID, or mention ID (Subject).")
    source_type: str = Field(
        description="Node type of source (e.g. ORGANIZATION, DOCUMENT, TRANSACTION)."
    )
    source_label: str = Field(description="Human-readable label for source node.")
    target_id: str = Field(description="Target entity ID, document ID, or mention ID (Object).")
    target_type: str = Field(description="Node type of target (e.g. INVOICE, DOCUMENT, PERSON).")
    target_label: str = Field(description="Human-readable label for target node.")
    direction_display: str = Field(
        description="Explicit directed relationship string: 'Subject --PREDICATE--> Object'."
    )
    status: RelationshipStatus
    status_determination_method: StatusDeterminationMethod = (
        StatusDeterminationMethod.EVIDENTIARY_RULE
    )
    duplicate_kind: DuplicateKind | None = None
    score: float = Field(ge=0.0, le=1.0)
    score_semantics: str
    detection_method: RelationshipDetectionMethod
    detection_version: str = "2.0.0"
    status_rationale: str
    evidence: RelationshipEvidence
    is_human_reviewed: bool = False
    human_review_status: str | None = None
    review_history: list[RelationshipReviewRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RelationshipCandidate(BaseModel):
    """Candidate relationship evaluated during discovery before final confirmation or filtering."""

    candidate_id: str = Field(default_factory=generate_id)
    relationship_type: RelationshipType
    ontology_version: str = "2.0"
    legacy_relationship_type: str | None = None
    source_id: str
    source_type: str
    source_label: str
    target_id: str
    target_type: str
    target_label: str
    status: RelationshipStatus
    status_determination_method: StatusDeterminationMethod = (
        StatusDeterminationMethod.EVIDENTIARY_RULE
    )
    duplicate_kind: DuplicateKind | None = None
    score: float = Field(ge=0.0, le=1.0)
    score_semantics: str
    evidence: RelationshipEvidence


class RelationshipDetectionRun(BaseModel):
    """Audit and execution metadata for a relationship detection run."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    pipeline_name: str = "cross_document_relationship_engine"
    pipeline_version: str = "2.0.0"
    ontology_version: str = "2.0"
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    total_documents: int = 0
    total_entities: int = 0
    relationships_detected: int = 0
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None


class RelationshipDetectionResult(BaseModel):
    """Aggregate result of a relationship detection run on a case."""

    case_id: str
    detection_run_id: str
    ontology_version: str = "2.0"
    relationships: list[DetectedRelationship] = Field(default_factory=list)
    summary_by_type: dict[str, int] = Field(default_factory=dict)
    summary_by_status: dict[str, int] = Field(default_factory=dict)
    unsupported_relationship_types: list[str] = Field(default_factory=list)
    detection_duration_ms: float = 0.0
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None
