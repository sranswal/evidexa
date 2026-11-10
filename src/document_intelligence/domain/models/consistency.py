"""Domain models for deterministic cross-document consistency analysis, evidentiary comparison, and human review."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import (
    ConsistencyDetectionMethod,
    ConsistencyOutcome,
    ConsistencyReviewAction,
    DocumentClass,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    PipelineStatus,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.bounding_box import BoundingBox


class ConsistencyComparison(BaseModel):
    """Atomic comparison between fields from two distinct documents."""

    field_key: str
    source_doc_id: str
    source_value: Any = None
    target_doc_id: str
    target_value: Any = None
    comparison_type: str = Field(
        description="Type of comparison (e.g. DECIMAL_MONETARY, STRING_EXACT, NORMALIZED_IDENTITY, DATE_SEQUENCE)."
    )
    outcome: ConsistencyOutcome
    difference: str | None = Field(
        default=None,
        description="Explicit string representation of discrepancy (e.g. '1000.00 INR difference').",
    )
    explanation: str = Field(
        description="Explainable rationale for this specific field comparison."
    )


class ConsistencyEvidenceLocation(BaseModel):
    """Traceable document location and extracted field provenance for consistency evidence."""

    document_id: str
    field_key: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    evidence_node_id: str | None = None
    raw_value: str | None = None
    normalized_value: str | None = None


class ConsistencyEvidence(BaseModel):
    """Aggregate traceable supporting and contradicting evidentiary signals for a consistency finding."""

    locations: list[ConsistencyEvidenceLocation] = Field(default_factory=list)
    supporting_evidence_node_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_node_ids: list[str] = Field(default_factory=list)
    comparisons: list[ConsistencyComparison] = Field(default_factory=list)
    detection_method: ConsistencyDetectionMethod = (
        ConsistencyDetectionMethod.DETERMINISTIC_FIELD_COMPARISON
    )
    detection_version: str = "1.0.0"


class ConsistencyReview(BaseModel):
    """Human investigator review record preserving decision history without erasing algorithmic evidence."""

    id: str = Field(default_factory=generate_id)
    finding_id: str
    case_id: str
    decision: ConsistencyReviewAction
    reviewer_id: str = Field(
        description="Asserted reviewer identifier in development mode (unauthenticated identity)."
    )
    reason: str = Field(min_length=1, max_length=1000)
    reviewed_at: datetime = Field(default_factory=utc_now)
    previous_status: str
    new_status: str


class ConsistencyFinding(BaseModel):
    """A cross-document consistency finding with complete evidence traceability and explainability.

    NOTE: Findings represent analytical inconsistencies or potential anomalies, NOT judicial fraud determinations.
    """

    id: str = Field(default_factory=generate_id)
    case_id: str
    analysis_run_id: str
    rule_id: str
    rule_version: str = "1.0.0"
    category: FindingCategory = FindingCategory.CROSS_DOCUMENT_MISMATCH
    title: str = Field(min_length=1, max_length=255)
    explanation: str = Field(max_length=4000)
    severity: FindingSeverity = FindingSeverity.MEDIUM
    outcome: ConsistencyOutcome
    score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Deterministic heuristic strength or rule ranking score. Never calibrated probability.",
    )
    score_semantics: str = "rule_deterministic_confidence"
    affected_document_ids: list[str] = Field(default_factory=list)
    compared_fields: list[str] = Field(default_factory=list)
    original_values: dict[str, Any] = Field(default_factory=dict)
    normalized_values: dict[str, Any] = Field(default_factory=dict)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    locations: list[ConsistencyEvidenceLocation] = Field(default_factory=list)
    detection_method: ConsistencyDetectionMethod = (
        ConsistencyDetectionMethod.DETERMINISTIC_FIELD_COMPARISON
    )
    rule_parameters: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    status: FindingStatus = FindingStatus.DETECTED
    review_status: str = "UNREVIEWED"
    is_human_reviewed: bool = False
    comparisons: list[ConsistencyComparison] = Field(default_factory=list)
    review_history: list[ConsistencyReview] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ConsistencyCheck(BaseModel):
    """A discrete consistency check performed between documents."""

    check_id: str = Field(default_factory=generate_id)
    rule_id: str
    document_ids: list[str] = Field(default_factory=list)
    outcome: ConsistencyOutcome
    explanation: str
    comparisons: list[ConsistencyComparison] = Field(default_factory=list)


class ConsistencyRule(BaseModel):
    """Metadata specification of a registered cross-document consistency rule."""

    rule_id: str
    rule_version: str = "1.0.0"
    rule_name: str
    description: str
    supported_document_types: list[DocumentClass] = Field(default_factory=list)
    required_field_keys: list[str] = Field(default_factory=list)
    category: FindingCategory
    default_severity: FindingSeverity


class ConsistencyAnalysisRun(BaseModel):
    """Audit and execution metadata for a cross-document consistency analysis run."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    document_ids: list[str] = Field(default_factory=list)
    pipeline_name: str = "cross_document_consistency_engine"
    pipeline_version: str = "1.0.0"
    status: PipelineStatus = PipelineStatus.RUNNING
    rules_applied: list[str] = Field(default_factory=list)
    total_findings: int = 0
    outcomes_summary: dict[str, int] = Field(default_factory=dict)
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    duration_ms: float = 0.0


class ConsistencyAnalysisResult(BaseModel):
    """Aggregate result payload of a consistency analysis run on a case."""

    case_id: str
    analysis_run_id: str
    status: PipelineStatus
    findings: list[ConsistencyFinding] = Field(default_factory=list)
    total_findings: int = 0
    outcomes_summary: dict[str, int] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None
