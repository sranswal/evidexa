"""Domain models for Optical Character Recognition (OCR) and Document Understanding.

Defines normalized contracts for token-level bounding boxes, line reconstruction,
reading order, layout blocks, tabular grids, engine provenance, multilingual script
attribution, hybrid PDF extraction, and traceable normalization.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from document_intelligence.domain.enums import (
    CoordinateSystem,
    LayoutRegionType,
    NormalizationForm,
    PageRoutingDecision,
    ScriptType,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry

CURRENT_ARTIFACT_SCHEMA_VERSION = "2.0.0"
LEGACY_ARTIFACT_SCHEMA_VERSION = "1.0.0"
SUPPORTED_ARTIFACT_MAJOR_VERSIONS = {1, 2}

# Maximum string length limits protecting against denial-of-service / memory exhaustion
MAX_TOKEN_TEXT_LENGTH = 10_000
MAX_LINE_TEXT_LENGTH = 100_000
MAX_PAGE_TEXT_LENGTH = 5_000_000
MAX_DOCUMENT_TEXT_LENGTH = 50_000_000


class OcrEngineMetadata(BaseModel):
    """Metadata describing the OCR/extraction engine and execution context."""

    engine_name: str = Field(min_length=1, max_length=100)
    engine_version: str = Field(min_length=1, max_length=50)
    model_id: str | None = Field(default=None, max_length=100)
    language: str = Field(default="en", max_length=50)
    dpi: float | None = Field(default=None, gt=0)

    # Extended multilingual provenance (Phase 4D.3.2)
    character_dict_name: str | None = Field(
        default=None,
        max_length=100,
        description="Identifier of character dictionary (e.g. 'devanagari_v5_dict.txt')",
    )
    model_artifacts: dict[str, str] = Field(
        default_factory=dict,
        description="Component-to-artifact mapping or cryptographic digests (e.g. {'rec': 'sha256:...'})",
    )
    runtime_name: str | None = Field(
        default=None,
        max_length=100,
        description="Underlying execution runtime (e.g. 'ONNXRuntime-CPU', 'PDFium')",
    )
    runtime_version: str | None = Field(
        default=None,
        max_length=50,
        description="Version of execution runtime",
    )
    execution_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("model_id", mode="before")
    @classmethod
    def sanitize_model_id(cls, v: Any) -> Any:
        """Strip local directory paths to prevent exposing host filesystem paths."""
        if isinstance(v, str) and ("/" in v or "\\" in v):
            return Path(v).name
        return v

    @field_validator("character_dict_name", mode="before")
    @classmethod
    def sanitize_dict_name(cls, v: Any) -> Any:
        """Strip local directory paths to prevent exposing host filesystem paths."""
        if isinstance(v, str) and ("/" in v or "\\" in v):
            return Path(v).name
        return v

    @field_validator("model_artifacts", mode="before")
    @classmethod
    def sanitize_model_artifacts(cls, v: Any) -> Any:
        """Strip local directory paths from artifact references."""
        if isinstance(v, dict):
            sanitized: dict[str, str] = {}
            for key, val in v.items():
                if isinstance(val, str) and ("/" in val or "\\" in val):
                    sanitized[str(key)] = Path(val).name
                else:
                    sanitized[str(key)] = str(val)
            return sanitized
        return v


class TextToken(BaseModel):
    """Atomic token-level extracted text element with bounding box and reading order."""

    id: str = Field(default_factory=generate_id)
    raw_text: str = Field(
        max_length=MAX_TOKEN_TEXT_LENGTH,
        description="Exact raw text as produced by engine, un-normalized",
    )
    normalized_text: str | None = Field(
        default=None,
        max_length=MAX_TOKEN_TEXT_LENGTH,
        description="Cleaned/normalized text for indexing and search",
    )
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Uncalibrated model recognition score [0.0 - 1.0], or None for vector text",
    )
    reading_order_index: int = Field(default=0, ge=0)
    is_coordinate_uncertain: bool = False
    coordinate_uncertainty_reason: str | None = Field(default=None, max_length=1000)

    # Extended multilingual and normalization provenance (Phase 4D.3.2)
    detected_script: ScriptType | str | None = Field(
        default=None,
        description="Classified script: 'DEVANAGARI', 'LATIN', 'NUMERIC', 'MIXED', 'PUNCTUATION', 'UNKNOWN'",
    )
    is_numeral_converted: bool = Field(
        default=False,
        description="True if normalized_text reflects Devanagari to ASCII numeral conversion",
    )
    normalization_form: NormalizationForm | str | None = Field(
        default=None,
        description="Unicode normalization standard applied (e.g. NFC)",
    )
    original_numeral_system: str | None = Field(
        default=None,
        max_length=50,
        description="Original numeral system before conversion (e.g. 'DEVANAGARI')",
    )
    original_raw_value: str | None = Field(
        default=None,
        max_length=MAX_TOKEN_TEXT_LENGTH,
        description="Exact original raw value preserved before normalization or conversion",
    )
    is_uncertain: bool = Field(
        default=False,
        description="Flag indicating uncertainty in token normalization or representation",
    )
    uncertainty_reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Explicit explanation for uncertainty",
    )

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 or None.")
        return v

    @field_validator("detected_script")
    @classmethod
    def validate_detected_script(cls, v: ScriptType | str | None) -> str | None:
        if v is None:
            return None
        val_str = v.value if isinstance(v, ScriptType) else str(v).upper()
        allowed = {s.value for s in ScriptType}
        if val_str not in allowed:
            raise ValueError(f"Invalid script identifier '{v}'. Must be one of {sorted(allowed)}.")
        return val_str

    @model_validator(mode="after")
    def validate_normalization_consistency(self) -> TextToken:
        if self.is_numeral_converted and self.normalized_text is None:
            raise ValueError("is_numeral_converted is True but normalized_text is None.")
        if self.is_uncertain and not self.uncertainty_reason:
            raise ValueError("is_uncertain is True but uncertainty_reason is missing.")
        return self


class TextLine(BaseModel):
    """Aggregated line of text containing an ordered sequence of tokens."""

    id: str = Field(default_factory=generate_id)
    raw_text: str = Field(max_length=MAX_LINE_TEXT_LENGTH)
    normalized_text: str | None = Field(default=None, max_length=MAX_LINE_TEXT_LENGTH)
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    tokens: list[TextToken] = Field(default_factory=list)
    reading_order_index: int = Field(default=0, ge=0)
    is_coordinate_uncertain: bool = False

    # Extended multilingual line provenance (Phase 4D.3.2)
    dominant_script: ScriptType | str | None = Field(
        default=None,
        description="Dominant script of line tokens: 'DEVANAGARI', 'LATIN', 'MIXED', 'NUMERIC'",
    )
    script_token_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of token counts by script in this line",
    )

    metadata: dict[str, Any] = Field(default_factory=dict)


class TextBlock(BaseModel):
    """Logical block or paragraph containing text lines."""

    id: str = Field(default_factory=generate_id)
    block_type: LayoutRegionType = LayoutRegionType.PARAGRAPH
    raw_text: str = Field(max_length=MAX_PAGE_TEXT_LENGTH)
    normalized_text: str | None = Field(default=None, max_length=MAX_PAGE_TEXT_LENGTH)
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
    raw_text: str = Field(default="", max_length=MAX_LINE_TEXT_LENGTH)
    normalized_text: str | None = Field(default=None, max_length=MAX_LINE_TEXT_LENGTH)
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


class AlternativeExtractionObservation(BaseModel):
    """Structured extraction observation representing an alternative layer on a page.

    Enables non-destructive coexistence of digital vector text (PDFium) and optical
    recognition (RapidOCR) on hybrid composite documents.
    """

    model_config = ConfigDict(extra="allow")

    engine_name: str = Field(default="unknown", max_length=100)
    extraction_method: str = Field(
        default="ALTERNATIVE_EXTRACTION",
        max_length=100,
        description="Method identifier (e.g. 'VECTOR_PDFIUM', 'OPTICAL_RAPIDOCR', 'HYBRID_FUSION')",
    )
    raw_text: str = Field(default="", max_length=MAX_PAGE_TEXT_LENGTH)
    normalized_text: str | None = Field(default=None, max_length=MAX_PAGE_TEXT_LENGTH)
    token_count: int = Field(default=0, ge=0)
    line_count: int = Field(default=0, ge=0)
    tokens: list[TextToken] = Field(default_factory=list)
    lines: list[TextLine] = Field(default_factory=list)
    coordinate_system: CoordinateSystem = Field(default=CoordinateSystem.NORMALIZED_0_1)
    geometry: PageGeometry | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        """Allow dictionary-like subscripting for backward compatibility with historical records."""
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.metadata:
            return self.metadata[item]
        extra = getattr(self, "__pydantic_extra__", None)
        if extra and item in extra:
            return extra[item]
        raise KeyError(item)

    def get(self, key: str, default: Any = None) -> Any:
        """Allow dictionary-like .get() for backward compatibility."""
        try:
            return self[key]
        except KeyError:
            return default


class ObservationDisagreement(BaseModel):
    """Evidentiary comparison between primary page extraction and an alternative observation."""

    primary_engine: str | None = None
    alternative_key: str
    alternative_engine: str | None = None
    primary_char_count: int = 0
    alternative_char_count: int = 0
    char_count_delta: int = 0
    primary_token_count: int = 0
    alternative_token_count: int = 0
    token_count_delta: int = 0
    has_disagreement: bool = False
    disagreement_reasons: list[str] = Field(default_factory=list)


class ExtractedPage(BaseModel):
    """Full extraction results for an individual document page."""

    page_number: int = Field(ge=1)
    geometry: PageGeometry
    raw_text: str = Field(default="", max_length=MAX_PAGE_TEXT_LENGTH)
    normalized_text: str = Field(default="", max_length=MAX_PAGE_TEXT_LENGTH)
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

    # Extended multilingual and hybrid routing fields (Phase 4D.3.2)
    script_distribution: dict[str, float] = Field(
        default_factory=dict,
        description="Distribution of characters by script: {'DEVANAGARI': 0.65, 'LATIN': 0.35}",
    )
    raster_area_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Ratio of page area covered by embedded raster images [0.0 - 1.0]",
    )
    vector_char_count: int | None = Field(
        default=None,
        ge=0,
        description="Count of digital vector characters extracted before routing or fallback",
    )
    disagreements: list[ObservationDisagreement] = Field(
        default_factory=list,
        description="Evidentiary discrepancies between primary extraction and alternative layers",
    )

    @model_validator(mode="after")
    def populate_disagreements(self) -> ExtractedPage:
        if not self.disagreements and self.alternative_extractions:
            self.disagreements = self.inspect_observation_disagreements()
        return self

    @field_validator("routing_decision")
    @classmethod
    def validate_routing_decision(cls, v: str | None) -> str | None:
        """Validate routing decision matches known canonical or legacy decisions."""
        if v is None:
            return None
        val_upper = v.upper()
        allowed = {d.value for d in PageRoutingDecision}
        if val_upper not in allowed:
            return v
        return val_upper

    def get_alternative_observation(self, key: str) -> AlternativeExtractionObservation | None:
        """Retrieve typed AlternativeExtractionObservation for an alternative extraction key."""
        raw = self.alternative_extractions.get(key)
        if raw is None:
            return None
        if isinstance(raw, AlternativeExtractionObservation):
            return raw
        if isinstance(raw, dict):
            return AlternativeExtractionObservation.model_validate(raw)
        return None

    def inspect_observation_disagreements(self) -> list[ObservationDisagreement]:
        """Inspect and report evidentiary disagreements between primary extraction and alternatives."""
        disagreements: list[ObservationDisagreement] = []
        p_chars = len(self.raw_text.strip())
        p_tokens = len(self.tokens)

        for key in self.alternative_extractions:
            alt_obs = self.get_alternative_observation(key)
            if not alt_obs:
                continue

            alt_chars = len(alt_obs.raw_text.strip())
            alt_tokens = alt_obs.token_count or len(alt_obs.tokens)
            char_delta = abs(p_chars - alt_chars)
            tok_delta = abs(p_tokens - alt_tokens)

            reasons: list[str] = []
            if p_chars == 0 and alt_chars > 0:
                reasons.append(
                    f"Primary extraction has zero characters but '{key}' has {alt_chars} characters."
                )
            elif alt_chars == 0 and p_chars > 0:
                reasons.append(
                    f"Primary extraction has {p_chars} characters but '{key}' has zero characters."
                )
            elif p_chars > 0 and char_delta > (max(p_chars, alt_chars) * 0.25):
                reasons.append(
                    f"Character count discrepancy: primary has {p_chars} chars, '{key}' has {alt_chars} chars (delta: {char_delta})."
                )

            if tok_delta > 10 and tok_delta > (max(p_tokens, alt_tokens) * 0.25):
                reasons.append(
                    f"Token count discrepancy: primary has {p_tokens} tokens, '{key}' has {alt_tokens} tokens (delta: {tok_delta})."
                )

            disagreements.append(
                ObservationDisagreement(
                    primary_engine=self.engine_name,
                    alternative_key=key,
                    alternative_engine=alt_obs.engine_name,
                    primary_char_count=p_chars,
                    alternative_char_count=alt_chars,
                    char_count_delta=char_delta,
                    primary_token_count=p_tokens,
                    alternative_token_count=alt_tokens,
                    token_count_delta=tok_delta,
                    has_disagreement=len(reasons) > 0,
                    disagreement_reasons=reasons,
                )
            )
        return disagreements


def _is_v2_payload(data: dict[str, Any]) -> bool:
    """Detect whether an unversioned payload contains v2-specific fields or models."""
    if data.get("script_summary"):
        return True
    meta = data.get("engine_metadata")
    if isinstance(meta, dict) and (
        meta.get("character_dict_name") or meta.get("model_artifacts") or meta.get("runtime_name")
    ):
        return True
    elif meta is not None and getattr(meta, "character_dict_name", None):
        return True
    pages = data.get("pages")
    if isinstance(pages, list):
        for p in pages:
            if isinstance(p, dict):
                if (
                    p.get("script_distribution")
                    or p.get("raster_area_ratio") is not None
                    or p.get("vector_char_count") is not None
                ):
                    return True
                for tok in p.get("tokens", []):
                    if isinstance(tok, dict) and (
                        tok.get("detected_script")
                        or tok.get("is_numeral_converted")
                        or tok.get("normalization_form")
                    ):
                        return True
            elif hasattr(p, "script_distribution") and p.script_distribution:
                return True
            elif hasattr(p, "raster_area_ratio") and p.raster_area_ratio is not None:
                return True
    return False


class ExtractedDocumentText(BaseModel):
    """Complete multi-page document extraction result and engine provenance."""

    schema_version: str = Field(
        default=CURRENT_ARTIFACT_SCHEMA_VERSION,
        description="Version of the OCR extracted document schema",
    )
    document_id: str
    processing_run_id: str
    engine_metadata: OcrEngineMetadata
    pages: list[ExtractedPage] = Field(default_factory=list)
    total_pages: int = 0
    total_tokens: int = 0
    full_raw_text: str = Field(default="", max_length=MAX_DOCUMENT_TEXT_LENGTH)
    full_normalized_text: str = Field(default="", max_length=MAX_DOCUMENT_TEXT_LENGTH)
    created_at: datetime = Field(default_factory=utc_now)
    storage_artifact_key: str | None = None
    storage_artifact_sha256: str | None = None

    # Aggregated document script statistics (Phase 4D.3.2)
    script_summary: dict[str, float] = Field(
        default_factory=dict,
        description="Aggregated distribution of characters across scripts for the entire document",
    )

    @classmethod
    def from_artifact_json(cls, json_str: str | bytes) -> ExtractedDocumentText:
        """Dedicated compatibility parser for loading historical or current OCR artifacts.

        Ensures historical artifacts without version tags load cleanly with legacy version 1.0.0,
        validates semantic versioning, and fails safely on unsupported future versions.
        """
        import json

        data = json.loads(json_str)
        return cls.from_artifact_dict(data)

    @classmethod
    def from_artifact_dict(cls, data: dict[str, Any]) -> ExtractedDocumentText:
        """Dedicated compatibility parser from a dictionary payload."""
        if not isinstance(data, dict):
            raise ValueError(f"Artifact payload must be a JSON object / dict, got {type(data)}.")
        data_copy = dict(data)
        if "schema_version" not in data_copy or not data_copy["schema_version"]:
            if _is_v2_payload(data_copy):
                data_copy["schema_version"] = CURRENT_ARTIFACT_SCHEMA_VERSION
            else:
                data_copy["schema_version"] = LEGACY_ARTIFACT_SCHEMA_VERSION
        return cls.model_validate(data_copy)

    @model_validator(mode="before")
    @classmethod
    def validate_schema_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Historical artifacts lack 'schema_version' -> infer based on payload contents
            version = data.get("schema_version")
            if not version:
                if _is_v2_payload(data):
                    data["schema_version"] = CURRENT_ARTIFACT_SCHEMA_VERSION
                else:
                    data["schema_version"] = LEGACY_ARTIFACT_SCHEMA_VERSION
                return data

            # 2. Check major version compatibility
            try:
                major_str = str(version).split(".")[0]
                major_ver = int(major_str)
            except Exception as err:
                raise ValueError(
                    f"Malformed OCR artifact schema_version: '{version}'. Must be semantic version (e.g. '2.0.0')."
                ) from err

            if major_ver not in SUPPORTED_ARTIFACT_MAJOR_VERSIONS:
                raise ValueError(
                    f"Unsupported OCR artifact schema_version '{version}'. "
                    f"Supported major versions: {sorted(SUPPORTED_ARTIFACT_MAJOR_VERSIONS)}."
                )
        return data


DEVANAGARI_DIGIT_MAP: dict[str, str] = {
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
}


def convert_devanagari_numerals(text: str) -> tuple[str, bool]:
    """Convert Devanagari numerals (०-९) to standard ASCII digits (0-9).

    Returns:
        tuple[converted_text, had_conversion]
    """
    if not text:
        return text, False

    converted_chars: list[str] = []
    had_conversion = False
    for ch in text:
        if ch in DEVANAGARI_DIGIT_MAP:
            converted_chars.append(DEVANAGARI_DIGIT_MAP[ch])
            had_conversion = True
        else:
            converted_chars.append(ch)

    return "".join(converted_chars), had_conversion


def classify_text_script(text: str) -> ScriptType:
    """Classify writing script based on Unicode codepoints.

    Categories:
    - DEVANAGARI: Text containing Devanagari letters without Latin
    - LATIN: Text containing Latin letters without Devanagari
    - MIXED: Text containing both Latin and Devanagari letters
    - NUMERIC: Numeric-only characters (ASCII digits or Devanagari numerals)
    - PUNCTUATION: Punctuation and symbols only
    - UNKNOWN: Empty or unclassified characters
    """
    if not text or not text.strip():
        return ScriptType.UNKNOWN

    devanagari_letter_count = 0
    latin_letter_count = 0
    digit_count = 0
    punctuation_count = 0

    for ch in text:
        cp = ord(ch)
        if (0x0900 <= cp <= 0x0963) or (0x0970 <= cp <= 0x097F) or (0xA8E0 <= cp <= 0xA8FF):
            # Devanagari letter/matra/sign (excluding Devanagari digits 0x0966-0x096F)
            devanagari_letter_count += 1
        elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A) or (0x00C0 <= cp <= 0x024F):
            # Latin letter (ASCII + Latin-1 Supplement + Latin Extended-A/B)
            latin_letter_count += 1
        elif (0x0030 <= cp <= 0x0039) or (0x0966 <= cp <= 0x096F):
            # ASCII digit or Devanagari numeral
            digit_count += 1
        elif ch.isspace():
            continue
        else:
            cat = unicodedata.category(ch)
            if cat.startswith("P") or cat.startswith("S"):
                punctuation_count += 1
            else:
                punctuation_count += 1

    total_meaningful = (
        devanagari_letter_count + latin_letter_count + digit_count + punctuation_count
    )
    if total_meaningful == 0:
        return ScriptType.UNKNOWN

    if devanagari_letter_count > 0 and latin_letter_count > 0:
        return ScriptType.MIXED
    if devanagari_letter_count > 0:
        return ScriptType.DEVANAGARI
    if latin_letter_count > 0:
        return ScriptType.LATIN
    if digit_count > 0 and punctuation_count == 0:
        return ScriptType.NUMERIC
    if (
        digit_count > 0
        and punctuation_count > 0
        and (devanagari_letter_count == 0 and latin_letter_count == 0)
    ):
        # Numeric with punctuation/symbols e.g. "1,234.50" or "₹१२,५००"
        return ScriptType.NUMERIC
    if punctuation_count > 0 and (
        devanagari_letter_count == 0 and latin_letter_count == 0 and digit_count == 0
    ):
        return ScriptType.PUNCTUATION

    return ScriptType.UNKNOWN


def create_traceable_token(
    raw_text: str,
    bounding_box: BoundingBox | None = None,
    confidence: float | None = None,
    reading_order_index: int = 0,
    is_coordinate_uncertain: bool = False,
    coordinate_uncertainty_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TextToken:
    """Construct a TextToken with deterministic Unicode NFC normalization and numeral traceability."""
    # 1. Base NFC canonical composition (preserves legal fractions and mathematical notations)
    nfc_text = unicodedata.normalize("NFC", raw_text)

    # 2. Deterministic script attribution
    script = classify_text_script(raw_text)

    # 3. Numeral transformation
    converted_text, had_conversion = convert_devanagari_numerals(nfc_text)

    # 4. Check for ambiguous or lossy transformations
    is_uncertain = is_coordinate_uncertain
    uncertainty_reason = coordinate_uncertainty_reason
    if "\ufffd" in raw_text:
        is_uncertain = True
        uncertainty_reason = (
            "Ambiguous Unicode replacement character (U+FFFD) detected in raw text."
        )
    else:
        for ch in raw_text:
            if unicodedata.category(ch) == "Cc" and ch not in ("\n", "\r", "\t"):
                is_uncertain = True
                uncertainty_reason = f"Control character (U+{ord(ch):04X}) detected in text."
                break

    if is_coordinate_uncertain and not coordinate_uncertainty_reason:
        coordinate_uncertainty_reason = "Uncertain bounding box coordinates."
    if is_uncertain and not uncertainty_reason:
        uncertainty_reason = (
            coordinate_uncertainty_reason or "Uncertain character normalization or coordinates."
        )

    applied_transformations: list[str] = []
    if nfc_text != raw_text:
        applied_transformations.append("unicode_nfc")
    if had_conversion:
        applied_transformations.append("devanagari_numerals")

    token_meta = dict(metadata or {})
    token_meta["normalization_version"] = "2.0.0"
    if applied_transformations:
        token_meta["applied_transformations"] = applied_transformations

    if had_conversion:
        token_meta["original_numeral_system"] = "DEVANAGARI"
        token_meta["raw_numeral_value"] = raw_text

    return TextToken(
        raw_text=raw_text,
        normalized_text=converted_text,
        bounding_box=bounding_box,
        confidence=confidence,
        reading_order_index=reading_order_index,
        is_coordinate_uncertain=is_coordinate_uncertain,
        coordinate_uncertainty_reason=coordinate_uncertainty_reason,
        detected_script=script,
        is_numeral_converted=had_conversion,
        normalization_form=NormalizationForm.NFC,
        original_numeral_system="DEVANAGARI" if had_conversion else None,
        original_raw_value=raw_text if had_conversion else None,
        is_uncertain=is_uncertain,
        uncertainty_reason=uncertainty_reason,
        metadata=token_meta,
    )
