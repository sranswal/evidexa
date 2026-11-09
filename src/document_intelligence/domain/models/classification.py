"""Domain models for document classification and page-level classification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import DocumentClass
from document_intelligence.domain.identifiers import utc_now


class ClassificationCandidate(BaseModel):
    """Ranked document class candidate with score and matched signals."""

    document_class: DocumentClass
    ranking_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Deterministic rule/ranking score. Explicitly uncalibrated probability.",
    )
    matched_signals: list[str] = Field(
        default_factory=list,
        description="Specific terms, patterns, or layout cues triggering match.",
    )


class PageClassification(BaseModel):
    """Classification outcome for a single document page."""

    page_number: int = Field(ge=1)
    predicted_class: DocumentClass
    ranking_score: float = Field(ge=0.0, le=1.0)
    candidates: list[ClassificationCandidate] = Field(default_factory=list)
    matched_signals: list[str] = Field(default_factory=list)


class ClassificationOverride(BaseModel):
    """Human review or investigator override preserving original machine prediction."""

    original_class: DocumentClass
    overridden_class: DocumentClass
    overridden_by: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)
    overridden_at: datetime = Field(default_factory=utc_now)


class DocumentClassificationResult(BaseModel):
    """Overall document classification result, candidate rankings, and page-level breakdown."""

    document_id: str
    processing_run_id: str
    predicted_class: DocumentClass
    effective_class: DocumentClass
    ranking_score: float = Field(ge=0.0, le=1.0)
    score_type: str = Field(
        default="rule_ranking_score",
        description="Explicit semantics of score ('rule_ranking_score', uncalibrated).",
    )
    classification_method: str = "rule_pattern_classifier_v1"
    classifier_version: str = "1.0.0"
    candidates: list[ClassificationCandidate] = Field(default_factory=list)
    page_classifications: list[PageClassification] = Field(default_factory=list)
    manual_override: ClassificationOverride | None = None
    execution_duration_ms: float = 0.0
    created_at: datetime = Field(default_factory=utc_now)
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
