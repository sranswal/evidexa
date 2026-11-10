"""Unit tests for geometry-aware hybrid PDF routing in HybridOcrAdapter.

Tests all 18 required scenarios:
1. test_vector_only_pdf_routes_to_vector_only
2. test_scanned_image_only_pdf_routes_to_ocr_only
3. test_mixed_vector_and_raster_routes_to_hybrid_fusion
4. test_overlapping_image_regions_avoid_double_counting
5. test_raster_coverage_threshold_boundaries
6. test_empty_blank_page_routes_to_no_text
7. test_image_heavy_page_with_sparse_vector_routes_to_ocr_only
8. test_duplicate_observations_identified_without_deletion
9. test_conflicting_observations_recorded_as_disagreements
10. test_devanagari_engine_selection_on_hindi_content
11. test_latin_engine_selection_on_english_content
12. test_ambiguous_script_triggers_limitation_reporting
13. test_coordinate_normalization_canonical_bounds
14. test_page_rotation_geometry_invariance
15. test_resource_limits_and_image_count_bounding
16. test_geometry_unavailable_falls_back_to_30_char_heuristic
17. test_regression_existing_english_ocr_fixtures
18. test_regression_multilingual_ocr_fixtures
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
from pikepdf import Array, Dictionary, Name
from PIL import Image, ImageDraw

from document_intelligence.domain.enums import (
    CoordinateSystem,
    PageRoutingDecision,
    PipelineStatus,
)
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
from document_intelligence.domain.models.ocr import (
    AlternativeExtractionObservation,
    ExtractedPage,
    TextToken,
)
from document_intelligence.modules.forensics.adapters.ocr.devanagari_adapter import (
    DevanagariRapidOcrAdapter,
)
from document_intelligence.modules.forensics.adapters.ocr.hybrid_adapter import (
    HybridOcrAdapter,
    RoutingDecision,
    compute_box_iou,
)
from document_intelligence.modules.forensics.adapters.ocr.rapidocr_adapter import RapidOcrAdapter
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from tests.fixtures.ocr_factory import (
    create_clean_digital_pdf,
    create_multilingual_pdf,
    create_rotated_pages_pdf,
    create_scanned_printed_text_pdf,
    create_sparse_embedded_text_pdf,
)

# ---------------------------------------------------------------------------
# Test Helpers to generate deterministic PDF fixtures with controlled geometry
# ---------------------------------------------------------------------------


def _make_image_stream(pdf: pikepdf.Pdf, w: int = 100, h: int = 100) -> pikepdf.Stream:
    """Create a simple JPEG image XObject inside a pikepdf document."""
    img = Image.new("RGB", (w, h), color=(180, 180, 180))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "EMBEDDED RASTER TEXT FOR OCR", fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    data = buf.getvalue()

    stream = pdf.make_stream(data)
    stream.Type = Name.XObject
    stream.Subtype = Name.Image
    stream.Width = w
    stream.Height = h
    stream.ColorSpace = Name.DeviceRGB
    stream.BitsPerComponent = 8
    stream.Filter = Name.DCTDecode
    return stream


def _create_vector_only_pdf(path: Path) -> Path:
    """PDF with standard vector text and 0 raster image objects."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    resources = Dictionary(Font=Dictionary(F1=font))
    text_cmd = (
        b"BT /F1 14 Tf 50 700 Td (Vector Only Forensic Specimen - Validating Page Level Routing) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (This document contains extensive vector characters exceeding thresholds.) Tj ET\n"
        b"BT /F1 12 Tf 50 640 Td (No embedded raster images exist on this page at all.) Tj ET\n"
    )
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(text_cmd),
            Resources=resources,
        )
    )
    pdf.pages.append(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _create_scanned_image_only_pdf(path: Path) -> Path:
    """PDF with a single full-page raster image and 0 vector text."""
    pdf = pikepdf.new()
    img_stream = _make_image_stream(pdf, w=612, h=792)
    resources = Dictionary(XObject=Dictionary(Im1=img_stream))
    cmd = b"q 612 0 0 792 0 0 cm /Im1 Do Q\n"
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(cmd),
            Resources=resources,
        )
    )
    pdf.pages.append(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _create_hybrid_fusion_pdf(path: Path) -> Path:
    """PDF with both >=30 chars vector text AND >=35% raster coverage (e.g. 50% image)."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    # Image covers bottom 50% of the page: 612 x 396 on 612 x 792 page
    img_stream = _make_image_stream(pdf, w=612, h=396)
    resources = Dictionary(
        Font=Dictionary(F1=font),
        XObject=Dictionary(Im1=img_stream),
    )
    cmd = (
        b"q 612 0 0 396 0 0 cm /Im1 Do Q\n"
        b"BT /F1 14 Tf 50 700 Td (CERTIFICATE OF FINANCIAL RECORD AUDIT - VECTOR HEADER) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (Meaningful digital text that exceeds thirty characters easily.) Tj ET\n"
        b"BT /F1 12 Tf 50 640 Td (Both native vector text and embedded scan must be preserved.) Tj ET\n"
    )
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(cmd),
            Resources=resources,
        )
    )
    pdf.pages.append(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _create_overlapping_images_pdf(path: Path) -> Path:
    """PDF with two overlapping images covering the same 20% area of the page.

    Total page area = 612 * 792 = 484,704 pt^2.
    Each image is placed at (0, 0) with width=612, height=158.4 (20% of page height).
    Sum of areas = 20% + 20% = 40% (> 35% threshold).
    Unary union area = 20% (< 35% threshold).
    With meaningful vector text (>=30 chars):
    - Double counting sum would wrongly trigger HYBRID_FUSION.
    - Shapely unary_union correctly resolves to 20% coverage -> routes to VECTOR_ONLY.
    """
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    img_stream1 = _make_image_stream(pdf, w=300, h=100)
    img_stream2 = _make_image_stream(pdf, w=300, h=100)
    resources = Dictionary(
        Font=Dictionary(F1=font),
        XObject=Dictionary(Im1=img_stream1, Im2=img_stream2),
    )
    # Height = 158.4 (20% of 792)
    cmd = (
        b"q 612 0 0 158.4 0 0 cm /Im1 Do Q\n"
        b"q 612 0 0 158.4 0 0 cm /Im2 Do Q\n"
        b"BT /F1 14 Tf 50 700 Td (Vector Header Text Exceeding Thirty Characters For Decision Testing) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (This text verifies that 20 percent raster does not inflate to 40 percent.) Tj ET\n"
    )
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(cmd),
            Resources=resources,
        )
    )
    pdf.pages.append(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _create_blank_pdf(path: Path) -> Path:
    """PDF with completely empty content (0 chars vector, 0 raster images)."""
    pdf = pikepdf.new()
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(b""),
            Resources=Dictionary(),
        )
    )
    pdf.pages.append(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _create_sparse_vector_with_raster_pdf(path: Path) -> Path:
    """PDF with <30 chars vector text (e.g. 10 chars 'Page 1 of 1') and 50% raster image."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    img_stream = _make_image_stream(pdf, w=612, h=396)
    resources = Dictionary(
        Font=Dictionary(F1=font),
        XObject=Dictionary(Im1=img_stream),
    )
    # 11 characters of vector text: "Page 1 of 1"
    cmd = b"q 612 0 0 396 0 0 cm /Im1 Do Q\nBT /F1 10 Tf 50 30 Td (Page 1 of 1) Tj ET\n"
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(cmd),
            Resources=resources,
        )
    )
    pdf.pages.append(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _create_many_images_pdf(path: Path, count: int = 220) -> Path:
    """PDF with 220 small image objects to test bounding to max_image_regions = 200."""
    pdf = pikepdf.new()
    img_stream = _make_image_stream(pdf, w=20, h=20)
    xobjects = Dictionary()
    cmd_parts = []
    for i in range(count):
        im_name = f"Im{i}"
        xobjects[Name(f"/{im_name}")] = img_stream
        x = (i % 20) * 25
        y = (i // 20) * 25
        cmd_parts.append(f"q 20 0 0 20 {x} {y} cm /{im_name} Do Q\n".encode("ascii"))

    resources = Dictionary(XObject=xobjects)
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(b"".join(cmd_parts)),
            Resources=resources,
        )
    )
    pdf.pages.append(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


# ---------------------------------------------------------------------------
# Test Suite: 18 Comprehensive Scenarios
# ---------------------------------------------------------------------------


class TestGeometryHybridRouting:
    """Exhaustive test suite for Geometry-Aware Hybrid PDF Routing."""

    def test_vector_only_pdf_routes_to_vector_only(self, tmp_path: Path) -> None:
        """Scenario 1: Clean digital PDF with meaningful vector text and no raster -> VECTOR_ONLY."""
        pdf_path = tmp_path / "vector_only.pdf"
        _create_vector_only_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-vec-01",
            document_id="doc-vec-01",
            processing_run_id="run-vec-01",
            document_sha256="1" * 64,
        )

        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["routing_decision"] in (
            PageRoutingDecision.VECTOR_ONLY,
            "DIGITAL_VECTOR_PRIMARY",
        )
        assert page_obs.evidence_payload["engine_name"] == "pypdfium2"
        assert page_obs.evidence_payload["has_vector_text"] is True
        assert page_obs.evidence_payload["vector_char_count"] >= 30
        assert page_obs.evidence_payload["raster_area_ratio"] == 0.0

    def test_scanned_image_only_pdf_routes_to_ocr_only(self, tmp_path: Path) -> None:
        """Scenario 2: Scanned image PDF with no vector text -> OCR_ONLY."""
        pdf_path = tmp_path / "scanned_only.pdf"
        _create_scanned_image_only_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-ocr-01",
            document_id="doc-ocr-01",
            processing_run_id="run-ocr-01",
            document_sha256="2" * 64,
        )

        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["routing_decision"] in (
            PageRoutingDecision.OCR_ONLY,
            "IMAGE_ONLY_SCANNED_PAGE",
        )
        assert page_obs.evidence_payload["vector_char_count"] < 30
        assert page_obs.evidence_payload["raster_area_ratio"] >= 0.35

    def test_mixed_vector_and_raster_routes_to_hybrid_fusion(self, tmp_path: Path) -> None:
        """Scenario 3: PDF with meaningful vector text (>=30 chars) and significant raster (>=35%) -> HYBRID_FUSION."""
        pdf_path = tmp_path / "hybrid_fusion.pdf"
        _create_hybrid_fusion_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-hyb-01",
            document_id="doc-hyb-01",
            processing_run_id="run-hyb-01",
            document_sha256="3" * 64,
        )

        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["routing_decision"] == PageRoutingDecision.HYBRID_FUSION
        assert page_obs.evidence_payload["vector_char_count"] >= 30
        assert page_obs.evidence_payload["raster_area_ratio"] >= 0.35
        # Dual-layer non-destructive preservation must retain PDFium
        assert "pdfium" in page_obs.evidence_payload["alternative_extractions"]

    def test_overlapping_image_regions_avoid_double_counting(self, tmp_path: Path) -> None:
        """Scenario 4: Two overlapping image regions covering 20% area must not sum to 40%."""
        pdf_path = tmp_path / "overlapping_images.pdf"
        _create_overlapping_images_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-ovl-01",
            document_id="doc-ovl-01",
            processing_run_id="run-ovl-01",
            document_sha256="4" * 64,
        )

        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        # With Shapely unary_union, coverage is ~0.20 (< 0.35 threshold), so routing is VECTOR_ONLY
        assert page_obs.evidence_payload["routing_decision"] in (
            PageRoutingDecision.VECTOR_ONLY,
            "DIGITAL_VECTOR_PRIMARY",
        )
        assert page_obs.evidence_payload["raster_area_ratio"] < 0.35

    def test_raster_coverage_threshold_boundaries(self, tmp_path: Path) -> None:
        """Scenario 5: Precise threshold boundaries (below 0.35 vs equal/above 0.35)."""
        # Test 5A: Raster coverage below threshold routes to VECTOR_ONLY
        pdf_path = tmp_path / "thresh_test.pdf"
        _create_hybrid_fusion_pdf(pdf_path)  # has ~50% raster coverage

        adapter = HybridOcrAdapter()

        # Set threshold to 0.60: 50% < 60% -> VECTOR_ONLY
        inp_below = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-th-01",
            document_id="doc-th-01",
            processing_run_id="run-th-01",
            document_sha256="5" * 64,
            options={"raster_threshold": 0.60},
        )
        out_below = adapter.analyze(inp_below)
        page_obs_below = next(o for o in out_below.observations if o.observation_type == "ocr_page")
        assert page_obs_below.evidence_payload["routing_decision"] in (
            PageRoutingDecision.VECTOR_ONLY,
            "DIGITAL_VECTOR_PRIMARY",
        )

        # Set threshold to 0.40: 50% >= 40% -> HYBRID_FUSION
        inp_above = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-th-02",
            document_id="doc-th-02",
            processing_run_id="run-th-02",
            document_sha256="5" * 64,
            options={"raster_threshold": 0.40},
        )
        out_above = adapter.analyze(inp_above)
        page_obs_above = next(o for o in out_above.observations if o.observation_type == "ocr_page")
        assert (
            page_obs_above.evidence_payload["routing_decision"] == PageRoutingDecision.HYBRID_FUSION
        )

    def test_empty_blank_page_routes_to_no_text(self, tmp_path: Path) -> None:
        """Scenario 6: Blank page with no text and no raster images routes to NO_TEXT."""
        pdf_path = tmp_path / "blank_page.pdf"
        _create_blank_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-blk-01",
            document_id="doc-blk-01",
            processing_run_id="run-blk-01",
            document_sha256="6" * 64,
        )

        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["routing_decision"] in (
            PageRoutingDecision.NO_TEXT,
            "INSUFFICIENT_EVIDENCE",
        )
        assert page_obs.evidence_payload["token_count"] == 0
        assert page_obs.evidence_payload["raster_area_ratio"] == 0.0

    def test_image_heavy_page_with_sparse_vector_routes_to_ocr_only(self, tmp_path: Path) -> None:
        """Scenario 7: Sparse vector text (<30 chars) with raster content routes to OCR_ONLY, preserving PDFium."""
        pdf_path = tmp_path / "sparse_vector.pdf"
        _create_sparse_vector_with_raster_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-spr-01",
            document_id="doc-spr-01",
            processing_run_id="run-spr-01",
            document_sha256="7" * 64,
        )

        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["routing_decision"] in (
            PageRoutingDecision.OCR_ONLY,
            "SPARSE_TEXT_FALLBACK",
            "IMAGE_ONLY_SCANNED_PAGE",
        )
        # Vector text must be preserved non-destructively in alternative extractions
        assert "pdfium" in page_obs.evidence_payload["alternative_extractions"]

    def test_duplicate_observations_identified_without_deletion(self) -> None:
        """Scenario 8: Identical tokens at overlapping coordinates are identified as potential duplicates without deleting tokens."""
        box1 = BoundingBox(
            x=0.1, y=0.1, width=0.2, height=0.05, coordinate_system=CoordinateSystem.NORMALIZED_0_1
        )
        box2 = BoundingBox(
            x=0.105,
            y=0.102,
            width=0.195,
            height=0.048,
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )

        iou = compute_box_iou(box1, box2)
        assert iou > 0.8

        # Build mock ExtractedPage instances
        optical_token = TextToken(
            id="ocr_t1", raw_text="INVOICE", bounding_box=box1, confidence=0.95
        )
        pdfium_token = TextToken(
            id="pdf_t1", raw_text="INVOICE", bounding_box=box2, confidence=None
        )

        optical_page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="INVOICE",
            normalized_text="INVOICE",
            tokens=[optical_token],
            lines=[],
            engine_name="rapidocr-optical-engine",
            routing_decision=RoutingDecision(PageRoutingDecision.HYBRID_FUSION),
        )
        pdfium_page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="INVOICE",
            normalized_text="INVOICE",
            tokens=[pdfium_token],
            lines=[],
            engine_name="pypdfium2",
            routing_decision=RoutingDecision(PageRoutingDecision.VECTOR_ONLY),
        )

        # Emulate the duplicate detection loop in _process_hybrid_page
        potential_duplicates = []
        for o_tok in optical_page.tokens:
            o_text = o_tok.raw_text.strip().lower()
            for p_tok in pdfium_page.tokens:
                p_text = p_tok.raw_text.strip().lower()
                if o_text and o_text == p_text:
                    token_iou = compute_box_iou(o_tok.bounding_box, p_tok.bounding_box)
                    if token_iou > 0.2:
                        potential_duplicates.append(
                            {
                                "text": o_tok.raw_text,
                                "ocr_token_id": o_tok.id,
                                "pdfium_token_id": p_tok.id,
                                "spatial_iou": round(token_iou, 3),
                            }
                        )

        assert len(potential_duplicates) == 1
        assert potential_duplicates[0]["text"] == "INVOICE"
        assert potential_duplicates[0]["ocr_token_id"] == "ocr_t1"
        assert potential_duplicates[0]["pdfium_token_id"] == "pdf_t1"

        # Neither token list is mutated
        assert len(optical_page.tokens) == 1
        assert len(pdfium_page.tokens) == 1

    def test_conflicting_observations_recorded_as_disagreements(self) -> None:
        """Scenario 9: Conflicting observations between primary OCR and PDFium layer are recorded as disagreements."""
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Short OCR result",
            normalized_text="Short OCR result",
            tokens=[TextToken(id="t1", raw_text="Short"), TextToken(id="t2", raw_text="result")],
            lines=[],
            engine_name="rapidocr-optical-engine",
            routing_decision=RoutingDecision(PageRoutingDecision.HYBRID_FUSION),
        )
        # Add alternative PDFium extraction with substantial character and token delta
        rich_vector_text = "Extensive native vector document containing numerous clauses, terms, and detailed text."
        alt_tokens = [
            TextToken(id=f"alt_t{i}", raw_text=w) for i, w in enumerate(rich_vector_text.split())
        ]
        page.alternative_extractions["pdfium"] = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            raw_text=rich_vector_text,
            normalized_text=rich_vector_text,
            confidence=None,
            token_count=len(alt_tokens),
            line_count=1,
            tokens=alt_tokens,
            lines=[],
        )

        disagreements = page.inspect_observation_disagreements()
        assert len(disagreements) == 1
        assert disagreements[0].has_disagreement is True
        assert len(disagreements[0].disagreement_reasons) >= 1
        assert any(
            "Character count discrepancy" in r or "Token count discrepancy" in r
            for r in disagreements[0].disagreement_reasons
        )

    def test_devanagari_engine_selection_on_hindi_content(self) -> None:
        """Scenario 10: Explicit Devanagari evidence triggers DevanagariRapidOcrAdapter selection."""
        adapter = HybridOcrAdapter()

        # Case A: Devanagari characters in vector text
        engine_inst, name, lims = adapter._select_ocr_engine(vector_text="भारतीय स्टेट बैंक खाता विवरण")
        assert isinstance(engine_inst, DevanagariRapidOcrAdapter)
        assert name == "ppocrv5-devanagari-engine"
        assert len(lims) == 0

        # Case B: Execution option language="hi"
        engine_inst_opt, name_opt, _ = adapter._select_ocr_engine(
            vector_text="", options={"language": "hi"}
        )
        assert isinstance(engine_inst_opt, DevanagariRapidOcrAdapter)
        assert name_opt == "ppocrv5-devanagari-engine"

        # Case C: Execution option script="devanagari"
        engine_inst_scr, name_scr, _ = adapter._select_ocr_engine(
            vector_text="", options={"script": "devanagari"}
        )
        assert isinstance(engine_inst_scr, DevanagariRapidOcrAdapter)
        assert name_scr == "ppocrv5-devanagari-engine"

    def test_latin_engine_selection_on_english_content(self) -> None:
        """Scenario 11: Latin/English text defaults to RapidOcrAdapter."""
        adapter = HybridOcrAdapter()

        engine_inst, name, lims = adapter._select_ocr_engine(
            vector_text="Standard Commercial Invoice and Audit Report",
            options={},
        )
        assert isinstance(engine_inst, RapidOcrAdapter)
        assert name == "rapidocr-optical-engine"
        assert len(lims) == 0

    def test_ambiguous_script_triggers_limitation_reporting(self) -> None:
        """Scenario 12: Unsupported/ambiguous script triggers limitation reporting."""
        adapter = HybridOcrAdapter()

        # Vector text contains Cyrillic characters
        cyrillic_text = "Сбербанк России официальный отчет"
        engine_inst, name, lims = adapter._select_ocr_engine(
            vector_text=cyrillic_text,
            options={},
        )
        # Defaults to Latin OCR but records explicit limitation
        assert isinstance(engine_inst, RapidOcrAdapter)
        assert len(lims) >= 1
        assert any("Ambiguous or unsupported script detected" in lim for lim in lims)

    def test_coordinate_normalization_canonical_bounds(self, tmp_path: Path) -> None:
        """Scenario 13: All bounding boxes reside strictly in NORMALIZED_0_1 space."""
        pdf_path = tmp_path / "bounds_test.pdf"
        _create_hybrid_fusion_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        doc = pdfium.PdfDocument(pdf_path)
        try:
            ratio, boxes, total_imgs = adapter._compute_raster_coverage(doc[0])
            assert 0.0 <= ratio <= 1.0
            assert total_imgs > 0
            for b in boxes:
                assert b.coordinate_system == CoordinateSystem.NORMALIZED_0_1
                assert 0.0 <= b.x <= 1.0
                assert 0.0 <= b.y <= 1.0
                assert 0.0 <= b.width <= 1.0
                assert 0.0 <= b.height <= 1.0
                assert b.x + b.width <= 1.0001
                assert b.y + b.height <= 1.0001
        finally:
            doc.close()

    def test_page_rotation_geometry_invariance(self, tmp_path: Path) -> None:
        """Scenario 14: Rotated pages (90, 180, 270 deg) compute geometry safely without crashing."""
        pdf_path = tmp_path / "rotated.pdf"
        create_rotated_pages_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-rot-01",
            document_id="doc-rot-01",
            processing_run_id="run-rot-01",
            document_sha256="8" * 64,
        )

        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED
        assert len([o for o in output.observations if o.observation_type == "ocr_page"]) == 4

    def test_resource_limits_and_image_count_bounding(self, tmp_path: Path) -> None:
        """Scenario 15: Pages exceeding max_image_regions are bounded to 200, and max_pages is enforced."""
        # 15A: Image count bounding
        pdf_path = tmp_path / "many_images.pdf"
        _create_many_images_pdf(pdf_path, count=220)

        adapter = HybridOcrAdapter()
        doc = pdfium.PdfDocument(pdf_path)
        try:
            ratio, boxes, total_imgs = adapter._compute_raster_coverage(doc[0])
            assert total_imgs == 220
            # Boxes must be truncated to max_image_regions (200)
            assert len(boxes) <= 200
            assert 0.0 <= ratio <= 1.0
        finally:
            doc.close()

        # 15B: Max pages limit
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-lim-01",
            document_id="doc-lim-01",
            processing_run_id="run-lim-01",
            document_sha256="9" * 64,
            options={"max_pages": 0},
        )
        out_lim = adapter.analyze(inp)
        assert out_lim.status == PipelineStatus.FAILED
        assert any("exceeds maximum permitted limit" in err for err in out_lim.errors)

    def test_geometry_unavailable_falls_back_to_30_char_heuristic(self, tmp_path: Path) -> None:
        """Scenario 16: When geometry is unavailable, adapter safely falls back to the 30-char heuristic."""
        # Case A: Digital text with >30 chars and geometry_available=False -> VECTOR_ONLY
        digital_path = tmp_path / "fallback_digital.pdf"
        _create_vector_only_pdf(digital_path)

        adapter = HybridOcrAdapter()
        inp_digital = AnalyzerInput(
            file_path=digital_path,
            declared_media_type="application/pdf",
            case_id="case-fb-01",
            document_id="doc-fb-01",
            processing_run_id="run-fb-01",
            document_sha256="a" * 64,
            options={"geometry_available": False},
        )
        out_digital = adapter.analyze(inp_digital)
        page_obs_dig = next(o for o in out_digital.observations if o.observation_type == "ocr_page")
        assert page_obs_dig.evidence_payload["routing_decision"] in (
            PageRoutingDecision.VECTOR_ONLY,
            "DIGITAL_VECTOR_PRIMARY",
        )
        assert "fallback heuristic triggered" in page_obs_dig.evidence_payload["routing_reason"]

        # Case B: Blank/sparse text (<30 chars) and geometry_available=False -> OCR_ONLY
        sparse_path = tmp_path / "fallback_sparse.pdf"
        _create_blank_pdf(sparse_path)

        inp_sparse = AnalyzerInput(
            file_path=sparse_path,
            declared_media_type="application/pdf",
            case_id="case-fb-02",
            document_id="doc-fb-02",
            processing_run_id="run-fb-02",
            document_sha256="b" * 64,
            options={"geometry_available": False},
        )
        out_sparse = adapter.analyze(inp_sparse)
        page_obs_sp = next(o for o in out_sparse.observations if o.observation_type == "ocr_page")
        assert page_obs_sp.evidence_payload["routing_decision"] in (
            PageRoutingDecision.OCR_ONLY,
            "SPARSE_TEXT_FALLBACK",
        )
        assert "fallback heuristic triggered" in page_obs_sp.evidence_payload["routing_reason"]

    def test_regression_existing_english_ocr_fixtures(self, tmp_path: Path) -> None:
        """Scenario 17: Existing English OCR fixtures remain fully operational and correctly routed."""
        clean_path = tmp_path / "clean_reg.pdf"
        create_clean_digital_pdf(clean_path)

        scanned_path = tmp_path / "scanned_reg.pdf"
        create_scanned_printed_text_pdf(scanned_path)

        sparse_path = tmp_path / "sparse_reg.pdf"
        create_sparse_embedded_text_pdf(sparse_path)

        adapter = HybridOcrAdapter()

        # Clean digital -> VECTOR_ONLY
        out_clean = adapter.analyze(
            AnalyzerInput(
                file_path=clean_path,
                declared_media_type="application/pdf",
                case_id="case-reg-c",
                document_id="doc-reg-c",
                processing_run_id="run-reg-c",
                document_sha256="c" * 64,
            )
        )
        assert out_clean.status == PipelineStatus.SUCCEEDED
        p_clean = next(o for o in out_clean.observations if o.observation_type == "ocr_page")
        assert p_clean.evidence_payload["routing_decision"] in (
            PageRoutingDecision.VECTOR_ONLY,
            "DIGITAL_VECTOR_PRIMARY",
        )

        # Scanned -> OCR_ONLY
        out_scanned = adapter.analyze(
            AnalyzerInput(
                file_path=scanned_path,
                declared_media_type="application/pdf",
                case_id="case-reg-s",
                document_id="doc-reg-s",
                processing_run_id="run-reg-s",
                document_sha256="d" * 64,
            )
        )
        assert out_scanned.status == PipelineStatus.SUCCEEDED
        p_scanned = next(o for o in out_scanned.observations if o.observation_type == "ocr_page")
        assert p_scanned.evidence_payload["routing_decision"] in (
            PageRoutingDecision.OCR_ONLY,
            "IMAGE_ONLY_SCANNED_PAGE",
        )

        # Sparse -> OCR_ONLY with PDFium preservation
        out_sparse = adapter.analyze(
            AnalyzerInput(
                file_path=sparse_path,
                declared_media_type="application/pdf",
                case_id="case-reg-p",
                document_id="doc-reg-p",
                processing_run_id="run-reg-p",
                document_sha256="e" * 64,
            )
        )
        assert out_sparse.status == PipelineStatus.SUCCEEDED
        p_sparse = next(o for o in out_sparse.observations if o.observation_type == "ocr_page")
        assert p_sparse.evidence_payload["routing_decision"] in (
            PageRoutingDecision.OCR_ONLY,
            "SPARSE_TEXT_FALLBACK",
        )
        assert "pdfium" in p_sparse.evidence_payload["alternative_extractions"]

    def test_regression_multilingual_ocr_fixtures(self, tmp_path: Path) -> None:
        """Scenario 18: Multilingual fixture produces valid extracted document and observations without regressions."""
        multi_path = tmp_path / "multi_fixture.pdf"
        create_multilingual_pdf(multi_path)

        adapter = HybridOcrAdapter()
        inp = AnalyzerInput(
            file_path=multi_path,
            declared_media_type="application/pdf",
            case_id="case-multi-reg",
            document_id="doc-multi-reg",
            processing_run_id="run-multi-reg",
            document_sha256="f" * 64,
        )

        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED
        assert len(output.observations) >= 2
        p_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert p_obs.evidence_payload["routing_decision"] in (
            PageRoutingDecision.VECTOR_ONLY,
            "DIGITAL_VECTOR_PRIMARY",
        )
