"""Domain models for Optical Character Recognition (OCR) and Document Understanding.

Defines normalized contracts for token-level bounding boxes, line reconstruction,
reading order, layout blocks, tabular grids, and engine provenance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from document_intelligence.domain.enums import LayoutRegionType
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry


class OcrEngineMetadata(BaseModel):
    """Metadata describing the OCR/extraction engine and execution context."""

    engine_name: str = Field(min_length=1, max_length=100)
    engine_version: str = Field(min_length=1, max_length=50)
    model_id: str | None = Field(default=None, max_length=100)
    language: str = Field(default="en", max_length=50)
    dpi: float | None = Field(default=None, gt=0)
    execution_params: dict[str, Any] = Field(default_factory=dict)


class TextToken(BaseModel):
    """Atomic token-level extracted text element with bounding box and reading order."""

    id: str = Field(default_factory=generate_id)
    raw_text: str = Field(description="Exact raw text as produced by engine, un-normalized")
    normalized_text: str | None = Field(
        default=None, description="Cleaned/normalized text for indexing and search"
    )
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reading_order_index: int = Field(default=0, ge=0)
    is_coordinate_uncertain: bool = False
    coordinate_uncertainty_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 or None.")
        return v


class TextLine(BaseModel):
    """Aggregated line of text containing an ordered sequence of tokens."""

    id: str = Field(default_factory=generate_id)
    raw_text: str
    normalized_text: str | None = None
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    tokens: list[TextToken] = Field(default_factory=list)
    reading_order_index: int = Field(default=0, ge=0)
    is_coordinate_uncertain: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextBlock(BaseModel):
    """Logical block or paragraph containing text lines."""

    id: str = Field(default_factory=generate_id)
    block_type: LayoutRegionType = LayoutRegionType.PARAGRAPH
    raw_text: str
    normalized_text: str | None = None
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    lines: list[TextLine] = Field(default_factory=list)
    reading_order_index: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedTableCell(BaseModel):
    """Atomic cell inside an extracted table grid."""

    id: str = Field(default_factory=generate_id)
    row_index: int = Field(ge=0)
    col_index: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    col_span: int = Field(default=1, ge=1)
    raw_text: str = ""
    normalized_text: str | None = None
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_header: bool = False
    tokens: list[TextToken] = Field(default_factory=list)


class ExtractedTable(BaseModel):
    """Structured table representation with rows, columns, and bounded cells."""

    id: str = Field(default_factory=generate_id)
    num_rows: int = Field(ge=0)
    num_cols: int = Field(ge=0)
    cells: list[ExtractedTableCell] = Field(default_factory=list)
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reading_order_index: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutRegion(BaseModel):
    """High-level semantic layout region (Header, Footer, Title, Paragraph, Table, Figure)."""

    id: str = Field(default_factory=generate_id)
    region_type: LayoutRegionType = LayoutRegionType.PARAGRAPH
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reading_order_index: int = Field(default=0, ge=0)
    associated_block_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedPage(BaseModel):
    """Full extraction results for an individual document page."""

    page_number: int = Field(ge=1)
    geometry: PageGeometry
    raw_text: str = ""
    normalized_text: str = ""
    tokens: list[TextToken] = Field(default_factory=list)
    lines: list[TextLine] = Field(default_factory=list)
    blocks: list[TextBlock] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)
    layout_regions: list[LayoutRegion] = Field(default_factory=list)
    has_vector_text: bool = True
    extraction_status: str = "SUCCEEDED"
    engine_name: str | None = None
    routing_decision: str | None = None
    routing_reason: str | None = None
    alternative_extractions: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class ExtractedDocumentText(BaseModel):
    """Complete multi-page document extraction result and engine provenance."""

    document_id: str
    processing_run_id: str
    engine_metadata: OcrEngineMetadata
    pages: list[ExtractedPage] = Field(default_factory=list)
    total_pages: int = 0
    total_tokens: int = 0
    full_raw_text: str = ""
    full_normalized_text: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None
