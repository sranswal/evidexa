"""Unit tests for OCR domain contracts, models, and coordinate representations."""

import json

import pytest
from pydantic import ValidationError

from document_intelligence.domain.enums import (
    CoordinateSystem,
    LayoutRegionType,
    NormalizationForm,
    PageRoutingDecision,
    ScriptType,
)
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
from document_intelligence.domain.models.ocr import (
    CURRENT_ARTIFACT_SCHEMA_VERSION,
    LEGACY_ARTIFACT_SCHEMA_VERSION,
    AlternativeExtractionObservation,
    ExtractedDocumentText,
    ExtractedPage,
    ExtractedTable,
    ExtractedTableCell,
    LayoutRegion,
    OcrEngineMetadata,
    TextBlock,
    TextLine,
    TextToken,
    classify_text_script,
    convert_devanagari_numerals,
    create_traceable_token,
)


class TestOcrDomainContracts:
    """Validate Pydantic domain models, nullable confidences, stable IDs, and hierarchy."""

    def test_token_model_invariants_and_nullable_confidence(self) -> None:
        box = BoundingBox(
            x=0.1, y=0.2, width=0.3, height=0.05, coordinate_system=CoordinateSystem.NORMALIZED_0_1
        )

        # 1. Nullable confidence
        token_none_conf = TextToken(raw_text="Invoice#", bounding_box=box, confidence=None)
        assert token_none_conf.confidence is None
        assert token_none_conf.raw_text == "Invoice#"
        assert len(token_none_conf.id) == 36  # Valid UUID string

        # 2. Honest calibrated confidence
        token_calibrated = TextToken(raw_text="Invoice#", bounding_box=box, confidence=0.95)
        assert token_calibrated.confidence == 0.95

        # 3. Invalid confidence rejected
        with pytest.raises(ValueError):
            TextToken(raw_text="Invalid", confidence=1.5)

    def test_text_line_hierarchy_and_token_containment(self) -> None:
        t1 = TextToken(raw_text="Total", reading_order_index=0)
        t2 = TextToken(raw_text="Amount:", reading_order_index=1)
        t3 = TextToken(raw_text="$4,500.00", reading_order_index=2)

        line = TextLine(
            raw_text="Total Amount: $4,500.00",
            tokens=[t1, t2, t3],
            reading_order_index=5,
        )

        assert line.raw_text == "Total Amount: $4,500.00"
        assert len(line.tokens) == 3
        assert line.reading_order_index == 5
        assert line.tokens[0].raw_text == "Total"
        assert line.tokens[2].raw_text == "$4,500.00"

    def test_text_block_and_layout_region_contracts(self) -> None:
        t1 = TextToken(raw_text="CONFIDENTIAL")
        line = TextLine(raw_text="CONFIDENTIAL", tokens=[t1])
        block = TextBlock(
            block_type=LayoutRegionType.HEADER,
            raw_text="CONFIDENTIAL",
            lines=[line],
            reading_order_index=0,
        )
        assert block.block_type == LayoutRegionType.HEADER
        assert len(block.lines) == 1

        region = LayoutRegion(
            region_type=LayoutRegionType.HEADER,
            associated_block_ids=[block.id],
            reading_order_index=0,
        )
        assert region.region_type == LayoutRegionType.HEADER
        assert region.associated_block_ids == [block.id]

    def test_extracted_table_and_cell_grid_contracts(self) -> None:
        cell_header = ExtractedTableCell(
            row_index=0,
            col_index=0,
            raw_text="Item",
            is_header=True,
        )
        cell_data = ExtractedTableCell(
            row_index=1,
            col_index=0,
            raw_text="Server License",
            is_header=False,
        )

        table = ExtractedTable(
            num_rows=2,
            num_cols=1,
            cells=[cell_header, cell_data],
        )

        assert table.num_rows == 2
        assert table.num_cols == 1
        assert len(table.cells) == 2
        assert table.cells[0].is_header is True
        assert table.cells[1].is_header is False
        assert table.cells[1].raw_text == "Server License"

    def test_extracted_document_text_serialization_roundtrip(self) -> None:
        meta = OcrEngineMetadata(
            engine_name="Google PDFium Engine",
            engine_version="1.0.0",
            language="en",
            dpi=150.0,
        )
        geom = PageGeometry(width=612.0, height=792.0, rotation=0, dpi=72.0)
        tok = TextToken(raw_text="Sample")
        page = ExtractedPage(
            page_number=1,
            geometry=geom,
            raw_text="Sample",
            normalized_text="sample",
            tokens=[tok],
            has_vector_text=True,
        )
        doc = ExtractedDocumentText(
            document_id="doc-123",
            processing_run_id="run-456",
            engine_metadata=meta,
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Sample",
            full_normalized_text="sample",
        )

        json_str = doc.model_dump_json()
        restored = ExtractedDocumentText.model_validate_json(json_str)

        assert restored.document_id == "doc-123"
        assert restored.engine_metadata.engine_name == "Google PDFium Engine"
        assert len(restored.pages) == 1
        assert restored.pages[0].tokens[0].raw_text == "Sample"
        assert restored.total_tokens == 1

    def test_uncertain_coordinates_preserves_provenance(self) -> None:
        tok = TextToken(
            raw_text="UncertainGlyph",
            bounding_box=None,
            is_coordinate_uncertain=True,
            coordinate_uncertainty_reason="Font matrix mapping missing glyph metrics",
        )
        assert tok.bounding_box is None
        assert tok.is_coordinate_uncertain is True
        assert tok.coordinate_uncertainty_reason is not None


class TestMultilingualOcrContracts:
    """Comprehensive tests for multilingual OCR domain contracts, observation coexistence, and normalization."""

    def test_historical_v1_artifact_backward_compatibility(self) -> None:
        """Historical v1 artifacts lacking schema_version must deserialize cleanly with legacy defaults."""
        v1_payload = {
            "document_id": "doc-hist-001",
            "processing_run_id": "run-hist-001",
            "engine_metadata": {
                "engine_name": "RapidOCR Latin",
                "engine_version": "1.0.0",
                "language": "en",
            },
            "pages": [
                {
                    "page_number": 1,
                    "geometry": {"width": 612.0, "height": 792.0, "rotation": 0, "dpi": 72.0},
                    "raw_text": "Invoice #4401",
                    "normalized_text": "Invoice #4401",
                    "tokens": [
                        {
                            "id": "tok-1",
                            "raw_text": "Invoice",
                            "reading_order_index": 0,
                        },
                        {
                            "id": "tok-2",
                            "raw_text": "#4401",
                            "reading_order_index": 1,
                        },
                    ],
                    "has_vector_text": False,
                    "alternative_extractions": {
                        "pdfium": {
                            "raw_text": "Inv #4401",
                            "token_count": 2,
                            "line_count": 1,
                            "sparse_threshold": 30,
                        }
                    },
                }
            ],
            "total_pages": 1,
            "total_tokens": 2,
            "full_raw_text": "Invoice #4401",
        }

        json_str = json.dumps(v1_payload)
        doc = ExtractedDocumentText.model_validate_json(json_str)

        # 1. Historical artifacts receive defined legacy version
        assert doc.schema_version == LEGACY_ARTIFACT_SCHEMA_VERSION
        assert doc.document_id == "doc-hist-001"
        assert len(doc.pages) == 1

        # 2. Tokens receive safe defaults for new multilingual fields
        page = doc.pages[0]
        tok1 = page.tokens[0]
        assert tok1.raw_text == "Invoice"
        assert tok1.detected_script is None
        assert tok1.is_numeral_converted is False
        assert tok1.normalization_form is None

        # 3. Alternative extractions support dictionary-like subscripting for backward compatibility
        assert "pdfium" in page.alternative_extractions
        assert page.alternative_extractions["pdfium"]["sparse_threshold"] == 30
        assert page.alternative_extractions["pdfium"]["raw_text"] == "Inv #4401"

    def test_current_multilingual_v2_artifact_roundtrip(self) -> None:
        """Current v2 artifacts serialize and deserialize with full multilingual and provenance fidelity."""
        meta = OcrEngineMetadata(
            engine_name="RapidOCR PP-OCRv5 Devanagari",
            engine_version="2.0.0",
            model_id="devanagari_PP-OCRv5_mobile_rec_infer.onnx",
            character_dict_name="devanagari_v5_dict.txt",
            model_artifacts={
                "det": "ch_PP-OCRv4_det_infer.onnx",
                "rec": "devanagari_PP-OCRv5_mobile_rec_infer.onnx",
            },
            runtime_name="ONNXRuntime-CPU",
            runtime_version="1.20.1",
            language="hi+en",
            dpi=150.0,
            execution_params={"box_thresh": 0.3, "unclip_ratio": 1.6, "use_cls": False},
        )
        geom = PageGeometry(width=800.0, height=1050.0, rotation=0, dpi=150.0)

        tok_hi = create_traceable_token("कुल:", reading_order_index=0)
        tok_num = create_traceable_token("₹१२,५००.००", reading_order_index=1)
        tok_en = create_traceable_token("INVOICE", reading_order_index=2)

        line = TextLine(
            raw_text="कुल: ₹१२,५००.०० INVOICE",
            normalized_text="कुल: ₹12,500.00 INVOICE",
            tokens=[tok_hi, tok_num, tok_en],
            dominant_script=ScriptType.MIXED,
            script_token_counts={"DEVANAGARI": 1, "NUMERIC": 1, "LATIN": 1},
        )

        alt_obs = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            extraction_method="VECTOR_PDFIUM",
            raw_text="TOTAL: INR 12,500.00 INVOICE",
            token_count=4,
            line_count=1,
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            metadata={"sparse_threshold": 30},
        )

        page = ExtractedPage(
            page_number=1,
            geometry=geom,
            raw_text="कुल: ₹१२,५००.०० INVOICE",
            normalized_text="कुल: ₹12,500.00 INVOICE",
            tokens=[tok_hi, tok_num, tok_en],
            lines=[line],
            routing_decision=PageRoutingDecision.HYBRID_FUSION,
            routing_reason="Raster image coverage 42.5% >= 35% threshold",
            raster_area_ratio=0.425,
            vector_char_count=28,
            script_distribution={"DEVANAGARI": 0.45, "LATIN": 0.35, "NUMERIC": 0.20},
            alternative_extractions={"pdfium": alt_obs},
        )

        doc = ExtractedDocumentText(
            document_id="doc-v2-001",
            processing_run_id="run-v2-001",
            engine_metadata=meta,
            pages=[page],
            total_pages=1,
            total_tokens=3,
            full_raw_text=page.raw_text,
            full_normalized_text=page.normalized_text,
            script_summary={"DEVANAGARI": 0.45, "LATIN": 0.35, "NUMERIC": 0.20},
        )

        json_bytes = doc.model_dump_json(indent=2)
        restored = ExtractedDocumentText.model_validate_json(json_bytes)

        assert restored.schema_version == CURRENT_ARTIFACT_SCHEMA_VERSION
        assert restored.engine_metadata.character_dict_name == "devanagari_v5_dict.txt"
        assert restored.pages[0].routing_decision == PageRoutingDecision.HYBRID_FUSION
        assert restored.pages[0].raster_area_ratio == 0.425
        assert restored.pages[0].vector_char_count == 28

        # Verify token restoration
        r_tokens = restored.pages[0].tokens
        assert r_tokens[0].raw_text == "कुल:"
        assert r_tokens[0].detected_script == ScriptType.DEVANAGARI
        assert r_tokens[1].raw_text == "₹१२,५००.००"
        assert r_tokens[1].normalized_text == "₹12,500.00"
        assert r_tokens[1].is_numeral_converted is True
        assert r_tokens[1].original_numeral_system == "DEVANAGARI"

        # Verify typed alternative extraction
        r_alt = restored.pages[0].get_alternative_observation("pdfium")
        assert r_alt is not None
        assert r_alt.engine_name == "pypdfium2"
        assert r_alt.raw_text == "TOTAL: INR 12,500.00 INVOICE"
        assert r_alt["sparse_threshold"] == 30

    def test_unknown_future_artifact_version_fails_safely(self) -> None:
        """Unsupported future major schema versions must fail safely with an informative error."""
        v3_payload = {
            "schema_version": "3.0.0",
            "document_id": "doc-v3",
            "processing_run_id": "run-v3",
            "engine_metadata": {"engine_name": "FutureEngine", "engine_version": "3.0"},
            "pages": [],
        }

        with pytest.raises(ValueError, match="Unsupported OCR artifact schema_version '3.0.0'"):
            ExtractedDocumentText.model_validate(v3_payload)

        # Malformed version string also fails safely
        malformed = dict(v3_payload, schema_version="non-semver")
        with pytest.raises(ValueError, match="Malformed OCR artifact schema_version"):
            ExtractedDocumentText.model_validate(malformed)

    def test_raw_text_immutability_and_traceable_normalization(self) -> None:
        """Raw text must remain strictly untouched byte-for-byte while normalization is recorded traceably."""
        raw_input = "चालान संख्या: ०५/२०२६"
        tok = create_traceable_token(raw_input)

        # Raw text is identical
        assert tok.raw_text == raw_input
        # Normalized text converts Devanagari numerals
        assert tok.normalized_text == "चालान संख्या: 05/2026"
        assert tok.is_numeral_converted is True
        assert tok.original_numeral_system == "DEVANAGARI"
        assert tok.original_raw_value == raw_input
        assert tok.normalization_form == NormalizationForm.NFC
        assert tok.detected_script == ScriptType.DEVANAGARI

    def test_unicode_nfc_preserves_fractions_and_superscripts(self) -> None:
        """Unicode NFC normalization preserves legal fractions and exponents without destructive decomposition."""
        raw_text = "Plot area: ½ m² / Volume: ¾ m³"
        tok = create_traceable_token(raw_text)

        assert tok.raw_text == raw_text
        assert tok.normalized_text == raw_text
        # Ensure '½' was NOT destructively decomposed into '1/2'
        assert "½" in tok.normalized_text
        assert "1/2" not in tok.normalized_text
        # Ensure '²' was NOT destructively decomposed into '2'
        assert "²" in tok.normalized_text

    def test_script_classification_accuracy(self) -> None:
        """Unicode codepoints deterministically classify scripts into defined categories."""
        # Latin
        assert classify_text_script("Invoice") == ScriptType.LATIN
        assert classify_text_script("VAT-REG-9901") == ScriptType.LATIN

        # Devanagari
        assert classify_text_script("मूल्यांकन") == ScriptType.DEVANAGARI
        assert classify_text_script("कर चालान") == ScriptType.DEVANAGARI

        # Mixed
        assert classify_text_script("GSTकर") == ScriptType.MIXED
        assert classify_text_script("PANकार्ड") == ScriptType.MIXED

        # Numeric (ASCII and Devanagari digits, with or without currency/punctuation)
        assert classify_text_script("98234") == ScriptType.NUMERIC
        assert classify_text_script("०९८२३४") == ScriptType.NUMERIC
        assert classify_text_script("₹12,500.00") == ScriptType.NUMERIC
        assert classify_text_script("₹१२,५००.००") == ScriptType.NUMERIC

        # Punctuation
        assert classify_text_script("---") == ScriptType.PUNCTUATION
        assert classify_text_script("::==") == ScriptType.PUNCTUATION

        # Unknown / Empty
        assert classify_text_script("") == ScriptType.UNKNOWN
        assert classify_text_script("   ") == ScriptType.UNKNOWN

    def test_convert_devanagari_numerals_accuracy(self) -> None:
        """Devanagari numerals ०-९ map to ASCII 0-9 exactly."""
        converted, had_conv = convert_devanagari_numerals("०१२३४५६७८९")
        assert converted == "0123456789"
        assert had_conv is True

        # Non-numeral text has False flag
        c2, had2 = convert_devanagari_numerals("English 1234")
        assert c2 == "English 1234"
        assert had2 is False

    def test_missing_and_uncalibrated_ocr_confidence_provenance(self) -> None:
        """OCR confidence represents uncalibrated model scores; vector text uses None."""
        # 1. Programmatic vector text has None confidence
        tok_vec = TextToken(raw_text="VectorWord", confidence=None)
        assert tok_vec.confidence is None

        # 2. Optical model score is preserved
        tok_ocr = TextToken(raw_text="OcrWord", confidence=0.8841)
        assert tok_ocr.confidence == 0.8841

        # 3. Invalid bounds rejected
        with pytest.raises(ValueError):
            TextToken(raw_text="Negative", confidence=-0.05)
        with pytest.raises(ValueError):
            TextToken(raw_text="Exceeds", confidence=1.01)

    def test_alternative_extraction_observation_coexistence(self) -> None:
        """Optical OCR and programmatic PDFium coexist on composite pages without text concatenation."""
        geom = PageGeometry(width=612.0, height=792.0, rotation=0, dpi=72.0)

        alt_pdfium = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            extraction_method="VECTOR_PDFIUM",
            raw_text="Header Text",
            token_count=2,
            metadata={"sparse_threshold": 30},
        )

        page = ExtractedPage(
            page_number=1,
            geometry=geom,
            raw_text="Scanned Optical Text in Body",
            normalized_text="Scanned Optical Text in Body",
            has_vector_text=True,
            engine_name="rapidocr-onnxruntime",
            routing_decision=PageRoutingDecision.HYBRID_FUSION,
            alternative_extractions={"pdfium": alt_pdfium},
        )

        # Primary extraction preserves optical tokens
        assert page.raw_text == "Scanned Optical Text in Body"
        # Alternative extraction preserves vector text
        assert "pdfium" in page.alternative_extractions
        assert page.alternative_extractions["pdfium"]["raw_text"] == "Header Text"
        assert page.alternative_extractions["pdfium"].get("token_count") == 2
        # No duplicate text concatenation
        assert "Header Text" not in page.raw_text

    def test_inspect_observation_disagreements(self) -> None:
        """Inspect observation disagreements between primary and alternative extraction layers."""
        geom = PageGeometry(width=612.0, height=792.0, rotation=0, dpi=72.0)

        # Alternative has 50 characters, but primary has 0 characters (disagreement)
        alt_obs = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            extraction_method="VECTOR_PDFIUM",
            raw_text="Digital Invoice #991204 issued to Global Finance Inc.",
            token_count=8,
        )

        page = ExtractedPage(
            page_number=1,
            geometry=geom,
            raw_text="",  # Optical dropped text
            normalized_text="",
            engine_name="rapidocr-onnxruntime",
            alternative_extractions={"pdfium": alt_obs},
        )

        disagreements = page.inspect_observation_disagreements()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.has_disagreement is True
        assert d.alternative_key == "pdfium"
        assert d.primary_char_count == 0
        assert d.alternative_char_count > 0
        assert any("zero characters" in r for r in d.disagreement_reasons)

    def test_coordinate_normalization_and_rotation_invariants(self) -> None:
        """Coordinates remain top-left NORMALIZED_0_1 and reject out-of-bounds coordinates."""
        valid_box = BoundingBox(
            x=0.05,
            y=0.10,
            width=0.40,
            height=0.08,
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )
        assert valid_box.coordinate_system == CoordinateSystem.NORMALIZED_0_1

        # Reject out of bounds (negative coordinate)
        with pytest.raises(ValueError):
            BoundingBox(
                x=-0.05,
                y=0.10,
                width=0.40,
                height=0.08,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            )

        # Reject out of bounds (width exceeds page)
        with pytest.raises(ValueError):
            BoundingBox(
                x=0.80,
                y=0.10,
                width=0.40,  # 0.80 + 0.40 = 1.20 > 1.0
                height=0.08,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            )

    def test_local_filesystem_path_sanitization_in_engine_metadata(self) -> None:
        """Local host directory paths must be stripped to prevent exposing internal filesystem paths."""
        meta = OcrEngineMetadata(
            engine_name="RapidOCR",
            engine_version="2.0.0",
            model_id="C:\\Users\\shubh\\models\\ocr\\devanagari_PP-OCRv5.onnx",
            character_dict_name="/var/data/dictionaries/devanagari_v5_dict.txt",
            model_artifacts={
                "det": "D:\\models\\ch_PP-OCRv4_det.onnx",
                "rec": "/opt/app/models/rec.onnx",
            },
        )

        assert meta.model_id == "devanagari_PP-OCRv5.onnx"
        assert meta.character_dict_name == "devanagari_v5_dict.txt"
        assert meta.model_artifacts["det"] == "ch_PP-OCRv4_det.onnx"
        assert meta.model_artifacts["rec"] == "rec.onnx"
        # Verify serialized JSON does not contain directories
        json_dump = meta.model_dump_json()
        assert "C:\\Users" not in json_dump
        assert "/var/data" not in json_dump

    def test_dedicated_compatibility_parser_loads_v1_and_v2(self) -> None:
        """The dedicated compatibility parser loads historical and modern artifacts reliably."""
        # 1. Historical unversioned JSON
        v1_raw = json.dumps(
            {
                "document_id": "doc-hist-p",
                "processing_run_id": "run-hist-p",
                "engine_metadata": {"engine_name": "Legacy", "engine_version": "1.0"},
                "pages": [],
            }
        )
        parsed_v1 = ExtractedDocumentText.from_artifact_json(v1_raw)
        assert parsed_v1.schema_version == LEGACY_ARTIFACT_SCHEMA_VERSION

        # 2. Modern v2 JSON
        v2_raw = json.dumps(
            {
                "schema_version": CURRENT_ARTIFACT_SCHEMA_VERSION,
                "document_id": "doc-v2-p",
                "processing_run_id": "run-v2-p",
                "engine_metadata": {"engine_name": "Modern", "engine_version": "2.0"},
                "pages": [],
            }
        )
        parsed_v2 = ExtractedDocumentText.from_artifact_json(v2_raw)
        assert parsed_v2.schema_version == CURRENT_ARTIFACT_SCHEMA_VERSION

    def test_security_bounds_and_oversized_payload_rejection(self) -> None:
        """Oversized inputs, invalid scripts, and out-of-range raster ratios are safely rejected."""
        # 1. Invalid script string
        with pytest.raises(ValueError, match="Invalid script identifier 'INVALID_SCRIPT'"):
            TextToken(raw_text="Word", detected_script="INVALID_SCRIPT")

        # 2. Oversized token raw text (> 10,000 characters)
        with pytest.raises(ValidationError):
            TextToken(raw_text="X" * 10_001)

        # 3. Invalid raster_area_ratio (> 1.0 or < 0.0)
        geom = PageGeometry(width=612.0, height=792.0, rotation=0, dpi=72.0)
        with pytest.raises(ValidationError):
            ExtractedPage(page_number=1, geometry=geom, raster_area_ratio=1.5)
        with pytest.raises(ValidationError):
            ExtractedPage(page_number=1, geometry=geom, raster_area_ratio=-0.1)

    def test_token_normalization_consistency_validation(self) -> None:
        """Token validation rejects inconsistent normalization flags and ungrounded uncertainty."""
        # 1. is_numeral_converted=True without normalized_text is inconsistent
        with pytest.raises(
            ValueError, match="is_numeral_converted is True but normalized_text is None"
        ):
            TextToken(raw_text="५००", normalized_text=None, is_numeral_converted=True)

        # 2. is_uncertain=True without uncertainty_reason is rejected
        with pytest.raises(
            ValueError, match="is_uncertain is True but uncertainty_reason is missing"
        ):
            TextToken(raw_text="Ambiguous", is_uncertain=True, uncertainty_reason=None)

        # 3. Valid uncertainty representation succeeds
        valid_uncertain = TextToken(
            raw_text="05/06/2024",
            is_uncertain=True,
            uncertainty_reason="Ambiguous endianness between DD/MM/YYYY and MM/DD/YYYY",
        )
        assert valid_uncertain.is_uncertain is True
        assert valid_uncertain.uncertainty_reason is not None
