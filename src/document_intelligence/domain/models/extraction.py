"""Domain models for structured field extraction, schemas, and field-level provenance."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator

from document_intelligence.domain.enums import (
    DocumentClass,
    FieldDataType,
    FieldValidationStatus,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.bounding_box import BoundingBox


class FieldDefinition(BaseModel):
    """Specification of an extractable field in an extraction schema."""

    field_key: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    data_type: FieldDataType
    is_required: bool = False
    description: str = ""
    validation_rules: list[str] = Field(default_factory=list)


class ExtractionSchema(BaseModel):
    """Versioned schema defining expected fields for a document class."""

    schema_id: str = Field(min_length=1, max_length=100)
    document_class: DocumentClass
    version: str = "1.0.0"
    description: str = ""
    fields: list[FieldDefinition] = Field(default_factory=list)


class CandidateValue(BaseModel):
    """Alternative candidate value found during field extraction."""

    raw_text: str
    normalized_value: Any
    score: float = Field(ge=0.0, le=1.0)
    page_number: int = Field(ge=1)
    bounding_box: BoundingBox | None = None
    token_ids: list[str] = Field(default_factory=list)
    data_type: FieldDataType | None = None

    @model_validator(mode="after")
    def coerce_decimal(self) -> CandidateValue:
        if (
            self.data_type in (FieldDataType.DECIMAL, FieldDataType.NUMBER)
            and self.normalized_value is not None
            and not isinstance(self.normalized_value, Decimal)
        ):
            try:
                self.normalized_value = Decimal(str(self.normalized_value))
            except Exception:
                pass
        return self


class ExtractedFieldValue(BaseModel):
    """Extracted field value with complete evidence provenance, bounding boxes, and validation."""

    id: str = Field(default_factory=generate_id)
    field_key: str
    label: str
    normalized_value: Any = None
    raw_text: str = ""
    data_type: FieldDataType
    extraction_method: str = "deterministic_pattern_v1"
    score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Deterministic rule/match score. Explicitly uncalibrated.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated probability (None for deterministic extraction).",
    )
    confidence_explanation: str | None = (
        "Deterministic pattern extraction has no calibrated probabilistic confidence."
    )
    source_document_id: str
    source_page_number: int = Field(ge=1)
    source_bounding_boxes: list[BoundingBox] = Field(default_factory=list)
    source_token_ids: list[str] = Field(default_factory=list)
    validation_status: FieldValidationStatus = FieldValidationStatus.UNVALIDATED
    warnings: list[str] = Field(default_factory=list)
    alternative_candidates: list[CandidateValue] = Field(default_factory=list)
    evidence_node_id: str | None = None

    @model_validator(mode="after")
    def coerce_decimal(self) -> ExtractedFieldValue:
        if (
            self.data_type in (FieldDataType.DECIMAL, FieldDataType.NUMBER)
            and self.normalized_value is not None
            and not isinstance(self.normalized_value, Decimal)
        ):
            try:
                self.normalized_value = Decimal(str(self.normalized_value))
            except Exception:
                pass
        return self


class DocumentExtractionResult(BaseModel):
    """Full structured extraction result for a document with schema and validation summary."""

    document_id: str
    processing_run_id: str
    document_class: DocumentClass
    schema_id: str
    schema_version: str = "1.0.0"
    fields: dict[str, ExtractedFieldValue] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    execution_duration_ms: float = 0.0
    created_at: datetime = Field(default_factory=utc_now)
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
