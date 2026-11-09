"""EvidenceNode entity representing atomic forensic evidence and OCR tokens."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from document_intelligence.domain.enums import CoordinateSystem, EvidenceType
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.bounding_box import BoundingBox


class EvidenceNode(BaseModel):
    """Atomic evidence record capturing visual, structural, or textual observations."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    document_id: str | None = None  # None for cross-document or case-level evidence
    processing_run_id: str
    evidence_type: EvidenceType
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(max_length=4000)
    source_component: str = Field(min_length=1, max_length=100)
    source_version: str = Field(min_length=1, max_length=50)
    observed_at: datetime = Field(default_factory=utc_now)
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    coordinate_system: CoordinateSystem | None = CoordinateSystem.NORMALIZED_0_1
    pdf_object_reference: str | None = Field(default=None, max_length=100)
    byte_offset_start: int | None = Field(default=None, ge=0)
    byte_offset_end: int | None = Field(default=None, ge=0)
    raw_value: str | None = Field(default=None, repr=False)  # Protected from logging repr
    normalized_value: str | None = None
    categorical_confidence: str | None = Field(default=None, max_length=50)
    confidence_source: str | None = Field(default=None, max_length=100)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 or None.")
        return value
