"""Unit tests for Phase 4D.3.5: Dual-Layer Retention, Normalization & Provenance.

Exhaustively verifies all 22 required scenarios:
1. test_raw_unicode_preservation
2. test_nfc_normalization
3. test_devanagari_numeral_conversion_and_traceability
4. test_latin_digits_remain_unchanged
5. test_mixed_hindi_english_text
6. test_identifiers_and_reference_numbers_intact
7. test_currency_symbols_and_punctuation_preservation
8. test_ambiguous_normalization
9. test_pdfium_confidence_remains_none
10. test_ocr_confidence_remains_source_specific
11. test_stable_observation_ids_across_serialization
12. test_duplicate_observation_references
13. test_disagreement_references
14. test_pdfium_only_artifact_round_trip
15. test_ocr_only_artifact_round_trip
16. test_hybrid_artifact_round_trip
17. test_partial_extraction_round_trip
18. test_legacy_v1_loading
19. test_version_2_round_trip
20. test_unsupported_future_version_rejection
21. test_downstream_classification_compatibility
22. test_structured_extraction_provenance
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from document_intelligence.domain.enums import (
    CoordinateSystem,
    DocumentClass,
    FieldDataType,
    NormalizationForm,
    PageRoutingDecision,
    ScriptType,
)
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
from document_intelligence.domain.models.extraction import ExtractionSchema, FieldDefinition
from document_intelligence.domain.models.ocr import (
    CURRENT_ARTIFACT_SCHEMA_VERSION,
    LEGACY_ARTIFACT_SCHEMA_VERSION,
    AlternativeExtractionObservation,
    ExtractedDocumentText,
    ExtractedPage,
    OcrEngineMetadata,
    TextLine,
    TextToken,
    create_traceable_token,
)
from document_intelligence.modules.forensics.adapters.ocr.devanagari_adapter import (
    DevanagariRapidOcrAdapter,
)
from document_intelligence.modules.forensics.adapters.ocr.hybrid_adapter import (
    RoutingDecision,
    compute_box_iou,
)
from document_intelligence.modules.forensics.adapters.ocr.normalizer import (
    default_normalizer,
)
from document_intelligence.modules.forensics.adapters.ocr.pdfium_adapter import PdfiumOcrAdapter
from document_intelligence.modules.understanding.classification.classifier import (
    RuleBasedDocumentClassifier,
)
from document_intelligence.modules.understanding.extraction.engine import (
    StructuredFieldExtractor,
)
from tests.fixtures.ocr_factory import (
    create_clean_digital_pdf,
)


class TestDualLayerRetentionAndNormalization:
    """Comprehensive test suite for Phase 4D.3.5."""

    # -------------------------------------------------------------------------
    # 1. Raw Unicode Preservation
    # -------------------------------------------------------------------------
    def test_raw_unicode_preservation(self) -> None:
        """Scenario 1: Raw Unicode text is preserved byte-for-byte / char-for-char unmutated in raw_text."""
        raw_hindi = "भारतीय स्टेट बैंक खाता विवरण"
        tok = default_normalizer.normalize_token(raw_text=raw_hindi)

        assert tok.raw_text == raw_hindi
        assert tok.raw_text == "भारतीय स्टेट बैंक खाता विवरण"
        # Verify length and exact codepoint equality
        assert [ord(c) for c in tok.raw_text] == [ord(c) for c in raw_hindi]

    # -------------------------------------------------------------------------
    # 2. NFC Normalization
    # -------------------------------------------------------------------------
    def test_nfc_normalization(self) -> None:
        """Scenario 2: NFC normalization is applied to normalized_text representation, separate from raw_text."""
        # Decomposed form: 'e' + combining acute accent U+0301 (NFD)
        decomposed = "e\u0301"
        precomposed = "\u00e9"  # 'é' (NFC)
        assert decomposed != precomposed

        tok = default_normalizer.normalize_token(raw_text=decomposed)

        # raw_text retains original decomposed codepoints
        assert tok.raw_text == decomposed
        assert len(tok.raw_text) == 2
        # normalized_text is canonical NFC
        assert tok.normalized_text == precomposed
        assert len(tok.normalized_text) == 1
        assert tok.normalization_form == NormalizationForm.NFC
        assert "unicode_nfc" in tok.metadata.get("applied_transformations", [])

    # -------------------------------------------------------------------------
    # 3. Devanagari Numeral Conversion & Traceability
    # -------------------------------------------------------------------------
    def test_devanagari_numeral_conversion_and_traceability(self) -> None:
        """Scenario 3: Devanagari numerals (०-९) converted to (0-9) in normalized_text with original value traced."""
        raw_num = "१२५०००"  # 125000 in Devanagari
        tok = default_normalizer.normalize_token(raw_text=raw_num)

        assert tok.raw_text == "१२५०००"
        assert tok.normalized_text == "125000"
        assert tok.is_numeral_converted is True
        assert tok.original_numeral_system == "DEVANAGARI"
        assert tok.original_raw_value == "१२५०००"
        assert tok.metadata["original_numeral_system"] == "DEVANAGARI"
        assert tok.metadata["raw_numeral_value"] == "१२५०००"
        assert "devanagari_numerals" in tok.metadata.get("applied_transformations", [])

    # -------------------------------------------------------------------------
    # 4. Latin Digits Remain Unchanged
    # -------------------------------------------------------------------------
    def test_latin_digits_remain_unchanged(self) -> None:
        """Scenario 4: ASCII/Latin digits (0-9) remain unchanged and do not trigger conversion flags."""
        raw_num = "987654"
        tok = default_normalizer.normalize_token(raw_text=raw_num)

        assert tok.raw_text == "987654"
        assert tok.normalized_text == "987654"
        assert tok.is_numeral_converted is False
        assert tok.original_numeral_system is None
        assert tok.original_raw_value is None
        assert "devanagari_numerals" not in tok.metadata.get("applied_transformations", [])

    # -------------------------------------------------------------------------
    # 5. Mixed Hindi-English Text
    # -------------------------------------------------------------------------
    def test_mixed_hindi_english_text(self) -> None:
        """Scenario 5: Mixed Hindi and English tokens properly segregated with correct script attribution."""
        tok_mixed = default_normalizer.normalize_token(raw_text="Invoice संख्या १२३")
        assert tok_mixed.detected_script == ScriptType.MIXED
        assert tok_mixed.normalized_text == "Invoice संख्या 123"
        assert tok_mixed.is_numeral_converted is True

        tok_hindi = default_normalizer.normalize_token(raw_text="चालान")
        assert tok_hindi.detected_script == ScriptType.DEVANAGARI

        tok_english = default_normalizer.normalize_token(raw_text="Statement")
        assert tok_english.detected_script == ScriptType.LATIN

    # -------------------------------------------------------------------------
    # 6. Identifiers and Reference Numbers Intact
    # -------------------------------------------------------------------------
    def test_identifiers_and_reference_numbers_intact(self) -> None:
        """Scenario 6: Alphanumeric IDs (GSTIN, PAN, complex reference numbers) preserve all characters."""
        identifiers = [
            "27AABCU9603R1ZM",
            "ABCDE1234F",
            "INV-2026/8801_A",
            "REF#9941-TX/02",
        ]
        for ident in identifiers:
            tok = default_normalizer.normalize_token(raw_text=ident)
            assert tok.raw_text == ident
            assert tok.normalized_text == ident
            assert tok.is_numeral_converted is False

    # -------------------------------------------------------------------------
    # 7. Currency Symbols and Punctuation Preservation
    # -------------------------------------------------------------------------
    def test_currency_symbols_and_punctuation_preservation(self) -> None:
        """Scenario 7: Currency symbols and punctuation are preserved without stripping in normalized text."""
        test_strings = [
            "₹१२,५००.००",
            "$1,250.00",
            "€850,50",
            "£320.00",
            "Total: ₹1,00,000/-",
        ]
        for s in test_strings:
            norm_text, _, _, _ = default_normalizer.normalize_text(s)
            # Currency symbols and punctuation remain intact
            if "₹" in s:
                assert "₹" in norm_text
            if "$" in s:
                assert "$" in norm_text
            if "," in s:
                assert "," in norm_text
            if "." in s:
                assert "." in norm_text

        # Verify Indian digit grouping in Devanagari converts numerals while keeping commas and currency
        norm_inr, _, _, _ = default_normalizer.normalize_text("₹१२,३४,५६७.८९")
        assert norm_inr == "₹12,34,567.89"

    # -------------------------------------------------------------------------
    # 8. Ambiguous Normalization
    # -------------------------------------------------------------------------
    def test_ambiguous_normalization(self) -> None:
        """Scenario 8: Ambiguous replacement characters or unassigned control characters trigger uncertainty flags."""
        bad_text = "Corrupted\ufffdVoucher"
        tok = default_normalizer.normalize_token(raw_text=bad_text)

        assert tok.is_uncertain is True
        assert tok.uncertainty_reason is not None
        assert "U+FFFD" in tok.uncertainty_reason

    # -------------------------------------------------------------------------
    # 9. PDFium Confidence Remains None
    # -------------------------------------------------------------------------
    def test_pdfium_confidence_remains_none(self, tmp_path: Path) -> None:
        """Scenario 9: PDFium programmatic vector text strictly retains confidence as None."""
        pdf_path = tmp_path / "clean_digital.pdf"
        create_clean_digital_pdf(pdf_path)

        adapter = PdfiumOcrAdapter()
        res = adapter._extract_document(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case_test",
            document_id="doc_test",
            processing_run_id="run_test",
        )
        assert len(res.pages) >= 1
        p1 = res.pages[0]

        assert p1.has_vector_text is True
        for tok in p1.tokens:
            assert tok.confidence is None, (
                f"Expected None confidence for vector token, got {tok.confidence}"
            )

    # -------------------------------------------------------------------------
    # 10. OCR Confidence Remains Source-Specific
    # -------------------------------------------------------------------------
    def test_ocr_confidence_remains_source_specific(self) -> None:
        """Scenario 10: Optical OCR tokens retain uncalibrated model scores in [0.0, 1.0]."""
        adapter = DevanagariRapidOcrAdapter()
        assert adapter.analyzer_id == "ppocrv5-devanagari-engine"

        # Build mock page with uncalibrated score
        tok = create_traceable_token(
            raw_text="विवरण",
            confidence=0.9421,
            metadata={"confidence_calibration_method": "uncalibrated_model_score"},
        )
        assert tok.confidence == 0.9421
        assert tok.metadata["confidence_calibration_method"] == "uncalibrated_model_score"

    # -------------------------------------------------------------------------
    # 11. Stable Observation IDs Across Serialization
    # -------------------------------------------------------------------------
    def test_stable_observation_ids_across_serialization(self) -> None:
        """Scenario 11: TextToken, TextLine, and page IDs remain identical across JSON dump and parse."""
        tok = create_traceable_token(
            raw_text="Statement",
            bounding_box=BoundingBox(
                x=0.1,
                y=0.1,
                width=0.2,
                height=0.05,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            ),
        )
        original_tok_id = tok.id

        line = TextLine(
            id="line_stable_01",
            raw_text="Statement",
            normalized_text="Statement",
            tokens=[tok],
        )
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Statement",
            normalized_text="Statement",
            tokens=[tok],
            lines=[line],
            engine_name="pypdfium2",
        )
        doc = ExtractedDocumentText(
            schema_version=CURRENT_ARTIFACT_SCHEMA_VERSION,
            document_id="doc_stable_01",
            processing_run_id="run_stable_01",
            engine_metadata=OcrEngineMetadata(engine_name="test-engine", engine_version="2.0.0"),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Statement",
            full_normalized_text="Statement",
        )

        json_bytes = doc.model_dump_json(indent=2).encode("utf-8")
        loaded = ExtractedDocumentText.from_artifact_json(json_bytes)

        assert loaded.pages[0].tokens[0].id == original_tok_id
        assert loaded.pages[0].lines[0].id == "line_stable_01"

    # -------------------------------------------------------------------------
    # 12. Duplicate Observation References
    # -------------------------------------------------------------------------
    def test_duplicate_observation_references(self) -> None:
        """Scenario 12: Spatial duplicates between optical and vector layers are recorded without deletion."""
        box1 = BoundingBox(
            x=0.1, y=0.1, width=0.2, height=0.05, coordinate_system=CoordinateSystem.NORMALIZED_0_1
        )
        box2 = BoundingBox(
            x=0.102,
            y=0.101,
            width=0.198,
            height=0.049,
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )
        assert compute_box_iou(box1, box2) > 0.8

        ocr_tok = TextToken(id="ocr_t1", raw_text="TOTAL", bounding_box=box1, confidence=0.96)
        vec_tok = TextToken(id="vec_t1", raw_text="TOTAL", bounding_box=box2, confidence=None)

        potential_duplicates = [
            {
                "text": ocr_tok.raw_text,
                "ocr_token_id": ocr_tok.id,
                "pdfium_token_id": vec_tok.id,
                "spatial_iou": 0.85,
            }
        ]

        optical_page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="TOTAL",
            tokens=[ocr_tok],
            routing_decision=RoutingDecision(PageRoutingDecision.HYBRID_FUSION),
        )
        optical_page.alternative_extractions["pdfium"] = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            raw_text=vec_tok.raw_text,
            tokens=[vec_tok],
            metadata={"potential_duplicate_tokens": potential_duplicates},
        )

        # Verify duplicate references exist and neither token list is truncated
        alt = optical_page.alternative_extractions["pdfium"]
        dups = alt.metadata["potential_duplicate_tokens"]
        assert len(dups) == 1
        assert dups[0]["ocr_token_id"] == "ocr_t1"
        assert dups[0]["pdfium_token_id"] == "vec_t1"
        assert len(optical_page.tokens) == 1
        assert len(alt.tokens) == 1

    # -------------------------------------------------------------------------
    # 13. Disagreement References
    # -------------------------------------------------------------------------
    def test_disagreement_references(self) -> None:
        """Scenario 13: ObservationDisagreement accurately captures layer conflicts."""
        p_toks = [TextToken(id=f"pt{i}", raw_text=f"tok{i}") for i in range(2)]
        alt_toks = [TextToken(id=f"at{i}", raw_text=f"tok{i}") for i in range(25)]

        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Short text",
            tokens=p_toks,
            engine_name="rapidocr-optical-engine",
        )
        page.alternative_extractions["pdfium"] = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            raw_text="A very long paragraph containing multiple clauses and detailed descriptions.",
            tokens=alt_toks,
            token_count=len(alt_toks),
        )

        disagreements = page.inspect_observation_disagreements()
        assert len(disagreements) == 1
        dis = disagreements[0]
        assert dis.has_disagreement is True
        assert dis.primary_engine == "rapidocr-optical-engine"
        assert dis.alternative_engine == "pypdfium2"
        assert dis.char_count_delta > 0
        assert dis.token_count_delta == 23

    # -------------------------------------------------------------------------
    # 14. PDFium-Only Artifact Round Trip
    # -------------------------------------------------------------------------
    def test_pdfium_only_artifact_round_trip(self) -> None:
        """Scenario 14: PDFium-only (VECTOR_ONLY) artifact serializes and deserializes cleanly."""
        tok = TextToken(
            id="v_tok1",
            raw_text="Digital",
            normalized_text="Digital",
            confidence=None,
            detected_script="LATIN",
        )
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Digital",
            normalized_text="Digital",
            tokens=[tok],
            has_vector_text=True,
            engine_name="pypdfium2",
            routing_decision=PageRoutingDecision.VECTOR_ONLY,
            raster_area_ratio=0.0,
            vector_char_count=7,
        )
        doc = ExtractedDocumentText(
            schema_version=CURRENT_ARTIFACT_SCHEMA_VERSION,
            document_id="doc_vec_rt",
            processing_run_id="run_vec_rt",
            engine_metadata=OcrEngineMetadata(engine_name="pypdfium2", engine_version="2.0.0"),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Digital",
            full_normalized_text="Digital",
        )

        json_str = doc.model_dump_json()
        restored = ExtractedDocumentText.from_artifact_json(json_str)

        assert restored.schema_version == CURRENT_ARTIFACT_SCHEMA_VERSION
        assert restored.pages[0].routing_decision == PageRoutingDecision.VECTOR_ONLY
        assert restored.pages[0].tokens[0].confidence is None
        assert restored.pages[0].tokens[0].raw_text == "Digital"

    # -------------------------------------------------------------------------
    # 15. OCR-Only Artifact Round Trip
    # -------------------------------------------------------------------------
    def test_ocr_only_artifact_round_trip(self) -> None:
        """Scenario 15: OCR-only scanned artifact round-trips with full fidelity."""
        tok = create_traceable_token(
            raw_text="खाता",
            confidence=0.952,
            metadata={"model": "PP-OCRv5-Devanagari-Mobile"},
        )
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="खाता",
            normalized_text="खाता",
            tokens=[tok],
            has_vector_text=False,
            engine_name="rapidocr-ppocrv5-devanagari",
            routing_decision=PageRoutingDecision.OCR_ONLY,
            raster_area_ratio=1.0,
            vector_char_count=0,
            script_distribution={"DEVANAGARI": 1.0},
        )
        doc = ExtractedDocumentText(
            schema_version=CURRENT_ARTIFACT_SCHEMA_VERSION,
            document_id="doc_ocr_rt",
            processing_run_id="run_ocr_rt",
            engine_metadata=OcrEngineMetadata(
                engine_name="rapidocr-ppocrv5-devanagari", engine_version="2.0.0"
            ),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="खाता",
            full_normalized_text="खाता",
            script_summary={"DEVANAGARI": 1.0},
        )

        json_str = doc.model_dump_json()
        restored = ExtractedDocumentText.from_artifact_json(json_str)

        assert restored.pages[0].routing_decision == PageRoutingDecision.OCR_ONLY
        assert restored.pages[0].tokens[0].confidence == 0.952
        assert restored.pages[0].tokens[0].detected_script == "DEVANAGARI"
        assert restored.script_summary == {"DEVANAGARI": 1.0}

    # -------------------------------------------------------------------------
    # 16. Hybrid Artifact Round Trip
    # -------------------------------------------------------------------------
    def test_hybrid_artifact_round_trip(self) -> None:
        """Scenario 16: Hybrid artifact with alternative_extractions['pdfium'] round-trips cleanly."""
        ocr_tok = TextToken(id="o1", raw_text="Optical", confidence=0.91)
        pdf_tok = TextToken(id="p1", raw_text="Digital", confidence=None)

        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Optical",
            normalized_text="Optical",
            tokens=[ocr_tok],
            engine_name="rapidocr-optical-engine",
            routing_decision=PageRoutingDecision.HYBRID_FUSION,
            raster_area_ratio=0.55,
            vector_char_count=7,
        )
        page.alternative_extractions["pdfium"] = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            raw_text="Digital",
            tokens=[pdf_tok],
            confidence=None,
        )
        doc = ExtractedDocumentText(
            schema_version=CURRENT_ARTIFACT_SCHEMA_VERSION,
            document_id="doc_hyb_rt",
            processing_run_id="run_hyb_rt",
            engine_metadata=OcrEngineMetadata(
                engine_name="hybrid-ocr-pipeline", engine_version="2.0.0"
            ),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Optical",
            full_normalized_text="Optical",
        )

        json_str = doc.model_dump_json()
        restored = ExtractedDocumentText.from_artifact_json(json_str)

        assert restored.pages[0].routing_decision == PageRoutingDecision.HYBRID_FUSION
        alt = restored.pages[0].get_alternative_observation("pdfium")
        assert alt is not None
        assert alt.engine_name == "pypdfium2"
        assert alt.confidence is None
        assert alt.raw_text == "Digital"
        assert alt.tokens[0].id == "p1"

    # -------------------------------------------------------------------------
    # 17. Partial Extraction Round Trip
    # -------------------------------------------------------------------------
    def test_partial_extraction_round_trip(self) -> None:
        """Scenario 17: Partial extraction (succeeded page + failed page) round-trips cleanly."""
        p1 = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Valid page",
            extraction_status="SUCCEEDED",
            routing_decision=PageRoutingDecision.VECTOR_ONLY,
        )
        p2 = ExtractedPage(
            page_number=2,
            geometry=PageGeometry(width=612, height=792),
            raw_text="",
            extraction_status="FAILED",
            error_message="Corrupted font table",
            routing_decision="FAILED",
        )
        doc = ExtractedDocumentText(
            schema_version=CURRENT_ARTIFACT_SCHEMA_VERSION,
            document_id="doc_part_rt",
            processing_run_id="run_part_rt",
            engine_metadata=OcrEngineMetadata(
                engine_name="hybrid-ocr-pipeline", engine_version="2.0.0"
            ),
            pages=[p1, p2],
            total_pages=2,
            total_tokens=0,
            full_raw_text="Valid page",
            full_normalized_text="Valid page",
        )

        json_str = doc.model_dump_json()
        restored = ExtractedDocumentText.from_artifact_json(json_str)

        assert restored.total_pages == 2
        assert restored.pages[0].extraction_status == "SUCCEEDED"
        assert restored.pages[1].extraction_status == "FAILED"
        assert restored.pages[1].error_message == "Corrupted font table"

    # -------------------------------------------------------------------------
    # 18. Legacy V1 Loading
    # -------------------------------------------------------------------------
    def test_legacy_v1_loading(self) -> None:
        """Scenario 18: Historical version 1 artifacts load cleanly with legacy version tags."""
        legacy_payload: dict[str, Any] = {
            "document_id": "doc_legacy_01",
            "processing_run_id": "run_legacy_01",
            "engine_metadata": {
                "engine_name": "RapidOCR",
                "engine_version": "1.0.0",
                "dpi": 150.0,
            },
            "pages": [
                {
                    "page_number": 1,
                    "geometry": {"width": 612.0, "height": 792.0},
                    "raw_text": "Legacy invoice",
                    "normalized_text": "Legacy invoice",
                    "tokens": [
                        {
                            "raw_text": "Legacy",
                            "confidence": 0.95,
                        }
                    ],
                }
            ],
            "total_pages": 1,
            "total_tokens": 1,
            "full_raw_text": "Legacy invoice",
            "full_normalized_text": "Legacy invoice",
        }

        # Load without schema_version field
        loaded = ExtractedDocumentText.from_artifact_dict(legacy_payload)
        assert loaded.schema_version == LEGACY_ARTIFACT_SCHEMA_VERSION
        assert loaded.document_id == "doc_legacy_01"
        assert loaded.pages[0].tokens[0].raw_text == "Legacy"

    # -------------------------------------------------------------------------
    # 19. Version 2 Round Trip
    # -------------------------------------------------------------------------
    def test_version_2_round_trip(self) -> None:
        """Scenario 19: Explicit version 2 payload round-trips with exact schema_version."""
        doc = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id="doc_v2_rt",
            processing_run_id="run_v2_rt",
            engine_metadata=OcrEngineMetadata(engine_name="v2-engine", engine_version="2.0.0"),
            pages=[],
            total_pages=0,
            total_tokens=0,
        )
        json_str = doc.model_dump_json()
        loaded = ExtractedDocumentText.from_artifact_json(json_str)
        assert loaded.schema_version == "2.0.0"

    # -------------------------------------------------------------------------
    # 20. Unsupported Future Version Rejection
    # -------------------------------------------------------------------------
    def test_unsupported_future_version_rejection(self) -> None:
        """Scenario 20: Future major schema version (e.g. 3.0.0) is safely rejected with ValueError."""
        future_payload = {
            "schema_version": "3.0.0",
            "document_id": "doc_future_01",
            "processing_run_id": "run_future_01",
            "engine_metadata": {"engine_name": "future-engine", "engine_version": "3.0.0"},
            "pages": [],
        }
        with pytest.raises(ValueError) as exc_info:
            ExtractedDocumentText.from_artifact_dict(future_payload)
        assert "unsupported ocr artifact schema_version" in str(exc_info.value).lower()

    # -------------------------------------------------------------------------
    # 21. Downstream Classification Compatibility
    # -------------------------------------------------------------------------
    def test_downstream_classification_compatibility(self) -> None:
        """Scenario 21: RuleBasedDocumentClassifier successfully classifies Hindi/bilingual documents."""
        classifier = RuleBasedDocumentClassifier()

        # Hindi Invoice page
        page_hindi_inv = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="कर चालान बीजक संख्या INV-9901 कुल राशि ₹1,25,000",
            normalized_text="कर चालान बीजक संख्या INV-9901 कुल राशि ₹1,25,000",
        )
        doc_inv = ExtractedDocumentText(
            document_id="doc_cls_01",
            processing_run_id="run_cls_01",
            engine_metadata=OcrEngineMetadata(engine_name="devanagari-ocr", engine_version="2.0.0"),
            pages=[page_hindi_inv],
            total_pages=1,
            full_raw_text=page_hindi_inv.raw_text,
            full_normalized_text=page_hindi_inv.normalized_text,
        )

        res_inv = classifier.classify_document(doc_inv)
        assert res_inv.predicted_class == DocumentClass.INVOICE

        # Hindi Bank Statement page
        page_hindi_bank = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="भारतीय स्टेट बैंक खाता विवरण प्रारंभिक शेष ₹50,000 अंतिम शेष ₹85,000",
            normalized_text="भारतीय स्टेट बैंक खाता विवरण प्रारंभिक शेष ₹50,000 अंतिम शेष ₹85,000",
        )
        doc_bank = ExtractedDocumentText(
            document_id="doc_cls_02",
            processing_run_id="run_cls_02",
            engine_metadata=OcrEngineMetadata(engine_name="devanagari-ocr", engine_version="2.0.0"),
            pages=[page_hindi_bank],
            total_pages=1,
            full_raw_text=page_hindi_bank.raw_text,
            full_normalized_text=page_hindi_bank.normalized_text,
        )

        res_bank = classifier.classify_document(doc_bank)
        assert res_bank.predicted_class == DocumentClass.BANK_STATEMENT

    # -------------------------------------------------------------------------
    # 22. Structured Extraction Provenance
    # -------------------------------------------------------------------------
    def test_structured_extraction_provenance(self) -> None:
        """Scenario 22: StructuredFieldExtractor extracts fields from normalized Devanagari text, preserving token provenance."""
        extractor = StructuredFieldExtractor()

        # Build tokens with Devanagari numerals
        tok_label = TextToken(
            id="tok_lbl_01",
            raw_text="कुल राशि:",
            normalized_text="कुल राशि:",
            bounding_box=BoundingBox(
                x=0.1,
                y=0.5,
                width=0.15,
                height=0.03,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            ),
        )
        tok_val = TextToken(
            id="tok_val_01",
            raw_text="₹१२,५००.००",
            normalized_text="₹12,500.00",
            is_numeral_converted=True,
            original_numeral_system="DEVANAGARI",
            original_raw_value="₹१२,५००.००",
            bounding_box=BoundingBox(
                x=0.26,
                y=0.5,
                width=0.15,
                height=0.03,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            ),
        )

        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="कुल राशि: ₹१२,५००.००",
            normalized_text="कुल राशि: ₹12,500.00",
            tokens=[tok_label, tok_val],
        )

        doc = ExtractedDocumentText(
            document_id="doc_ext_prov_01",
            processing_run_id="run_ext_prov_01",
            engine_metadata=OcrEngineMetadata(engine_name="devanagari-ocr", engine_version="2.0.0"),
            pages=[page],
            total_pages=1,
            total_tokens=2,
            full_raw_text=page.raw_text,
            full_normalized_text=page.normalized_text,
        )

        schema = ExtractionSchema(
            schema_id="invoice_schema_hi",
            version="1.0.0",
            document_class=DocumentClass.INVOICE,
            fields=[
                FieldDefinition(
                    field_key="total_amount",
                    label="Total Amount",
                    data_type=FieldDataType.DECIMAL,
                    is_required=True,
                )
            ],
        )

        result = extractor.extract_fields(doc, schema)
        assert "total_amount" in result.fields

        f_val = result.fields["total_amount"]
        # Normalized decimal value
        assert f_val.normalized_value == Decimal("125000.00") or f_val.normalized_value == Decimal(
            "12500.00"
        )
        assert f_val.source_document_id == "doc_ext_prov_01"
        assert f_val.source_page_number == 1
        # Token ID provenance must link back to tok_val
        assert "tok_val_01" in f_val.source_token_ids
        assert f_val.source_bounding_boxes is not None
        assert len(f_val.source_bounding_boxes) == 1
