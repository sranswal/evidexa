"""ForensicFinding entity representing an evidentiary interpretation or detected anomaly."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from document_intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from document_intelligence.domain.identifiers import generate_id, utc_now


class ForensicFinding(BaseModel):
    """Forensic finding supported by one or more atomic evidence records.

    NOTE: A finding represents an evidentiary anomaly, NOT a confirmed determination of fraud.
    """

    id: str = Field(default_factory=generate_id)
    case_id: str
    document_id: str | None = None
    processing_run_id: str
    category: FindingCategory
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(max_length=4000)
    severity: FindingSeverity
    categorical_confidence: str | None = Field(default=None, max_length=50)
    confidence_source: str | None = Field(default=None, max_length=100)
    confidence_calibration_method: str | None = Field(default=None, max_length=100)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: FindingStatus = Field(default=FindingStatus.DETECTED)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    source_component: str = Field(min_length=1, max_length=100)
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_supporting_evidence(self) -> "ForensicFinding":
        """Enforce that non-OTHER findings must cite at least one supporting evidence record."""
        if self.category != FindingCategory.OTHER and not self.evidence_ids:
            raise ValueError(
                f"Findings in category '{self.category.value}' must reference at least one supporting evidence ID."
            )
        return self
