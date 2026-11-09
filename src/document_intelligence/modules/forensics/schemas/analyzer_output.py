"""Schemas defining normalized output records produced by forensic analyzers."""

from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import CoordinateSystem, PipelineStatus
from document_intelligence.domain.identifiers import generate_id
from document_intelligence.domain.models.bounding_box import BoundingBox


class AnalyzerObservation(BaseModel):
    """Normalized observation extracted from an analyzer's execution."""

    id: str = Field(default_factory=generate_id)
    observation_type: str = Field(
        description="Subsystem observation category (e.g. structure, revisions, metadata)"
    )
    title: str
    description: str
    severity: str = Field(
        default="info", description="Severity label: info, low, medium, high, critical"
    )
    categorical_confidence: str | None = Field(
        default=None,
        description="Preserved verbatim categorical confidence label from source (e.g. 'high', 'medium', 'low', 'unknown')",
    )
    confidence_source: str | None = Field(
        default=None,
        description="Source component or methodology identifying confidence assessment",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated empirical probability only if source provides empirical calibration; otherwise None",
    )
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    coordinate_system: CoordinateSystem | None = None
    pdf_object_reference: str | None = None
    byte_offset_start: int | None = None
    byte_offset_end: int | None = None
    observed_value: str | None = None
    expected_value: str | None = None
    capability_id: str
    evidence_payload: dict[str, Any] = Field(default_factory=dict)
    benign_explanations: list[str] = Field(default_factory=list)


class AnalyzerCapabilityResult(BaseModel):
    """Result status for an individual capability check."""

    capability_id: str
    status: str = Field(description="PASS, FINDING, WARNING, UNSUPPORTED, or ERROR")
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class AnalyzerOutput(BaseModel):
    """Complete structured output returned by a ForensicAnalyzer."""

    analyzer_id: str
    analyzer_name: str
    analyzer_version: str
    status: PipelineStatus
    execution_duration_ms: float = 0.0
    capabilities_executed: list[AnalyzerCapabilityResult] = Field(default_factory=list)
    observations: list[AnalyzerObservation] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
