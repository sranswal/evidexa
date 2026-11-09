"""Unit tests for HybridOcrAdapter: page-level extraction routing and reconciliation."""

from pathlib import Path

from PIL import Image

from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.modules.forensics.adapters.ocr.hybrid_adapter import HybridOcrAdapter
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from tests.fixtures.ocr_factory import (
    create_clean_digital_pdf,
    create_mixed_digital_and_scanned_pdf,
    create_scanned_printed_text_pdf,
    create_sparse_embedded_text_pdf,
)


class TestHybridOcrRouting:
    """Verifies intelligent page-level extraction routing between PDFium and RapidOCR."""

    def test_clean_digital_pdf_routes_to_pdfium(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "digital.pdf"
        create_clean_digital_pdf(pdf_path)

        adapter = HybridOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-hyb-01",
            document_id="doc-hyb-01",
            processing_run_id="run-hyb-01",
            document_sha256="1" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["engine_name"] == "pypdfium2"
        assert page_obs.evidence_payload["routing_decision"] == "DIGITAL_VECTOR_PRIMARY"
        assert page_obs.evidence_payload["has_vector_text"] is True
        assert page_obs.evidence_payload["token_count"] > 10

    def test_scanned_page_routes_to_rapidocr(self, tmp_path: Path) -> None:
        scan_path = tmp_path / "scanned.pdf"
        create_scanned_printed_text_pdf(scan_path)

        adapter = HybridOcrAdapter()
        input_data = AnalyzerInput(
            file_path=scan_path,
            declared_media_type="application/pdf",
            case_id="case-hyb-02",
            document_id="doc-hyb-02",
            processing_run_id="run-hyb-02",
            document_sha256="2" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["engine_name"] == "rapidocr-onnxruntime"
        assert page_obs.evidence_payload["routing_decision"] == "IMAGE_ONLY_SCANNED_PAGE"
        assert page_obs.evidence_payload["token_count"] > 5

    def test_sparse_text_page_triggers_fallback_and_preserves_pdfium(self, tmp_path: Path) -> None:
        sparse_path = tmp_path / "sparse.pdf"
        create_sparse_embedded_text_pdf(sparse_path)

        adapter = HybridOcrAdapter(sparse_char_threshold=30)
        input_data = AnalyzerInput(
            file_path=sparse_path,
            declared_media_type="application/pdf",
            case_id="case-hyb-03",
            document_id="doc-hyb-03",
            processing_run_id="run-hyb-03",
            document_sha256="3" * 64,
            options={"sparse_threshold": 30},
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["engine_name"] == "rapidocr-onnxruntime"
        assert page_obs.evidence_payload["routing_decision"] == "SPARSE_TEXT_FALLBACK"
        # Preserves PDFium extraction
        assert "pdfium" in page_obs.evidence_payload["alternative_extractions"]

    def test_force_ocr_option_forces_rapidocr_on_digital_pdf(self, tmp_path: Path) -> None:
        digital_path = tmp_path / "force_digital.pdf"
        create_clean_digital_pdf(digital_path)

        adapter = HybridOcrAdapter()
        input_data = AnalyzerInput(
            file_path=digital_path,
            declared_media_type="application/pdf",
            case_id="case-hyb-04",
            document_id="doc-hyb-04",
            processing_run_id="run-hyb-04",
            document_sha256="4" * 64,
            options={"force_ocr": True},
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["engine_name"] == "rapidocr-onnxruntime"
        assert page_obs.evidence_payload["routing_decision"] == "FORCED_OPTICAL_OCR"
        assert "pdfium" in page_obs.evidence_payload["alternative_extractions"]

    def test_mixed_document_page_level_provenance(self, tmp_path: Path) -> None:
        mixed_path = tmp_path / "mixed.pdf"
        create_mixed_digital_and_scanned_pdf(mixed_path)

        adapter = HybridOcrAdapter()
        input_data = AnalyzerInput(
            file_path=mixed_path,
            declared_media_type="application/pdf",
            case_id="case-hyb-05",
            document_id="doc-hyb-05",
            processing_run_id="run-hyb-05",
            document_sha256="5" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = [o for o in output.observations if o.observation_type == "ocr_page"]
        assert len(page_obs) == 2

        # Page 1 must be digital PDFium
        p1 = page_obs[0]
        assert p1.page_number == 1
        assert p1.evidence_payload["engine_name"] == "pypdfium2"
        assert p1.evidence_payload["routing_decision"] == "DIGITAL_VECTOR_PRIMARY"

        # Page 2 must be scanned RapidOCR
        p2 = page_obs[1]
        assert p2.page_number == 2
        assert p2.evidence_payload["engine_name"] == "rapidocr-onnxruntime"
        assert p2.evidence_payload["routing_decision"] == "IMAGE_ONLY_SCANNED_PAGE"

    def test_direct_raster_image_routes_to_rapidocr(self, tmp_path: Path) -> None:
        img_path = tmp_path / "voucher.png"
        img = Image.new("RGB", (400, 150), color=(255, 255, 255))
        img.save(img_path)

        adapter = HybridOcrAdapter()
        input_data = AnalyzerInput(
            file_path=img_path,
            declared_media_type="image/png",
            detected_media_type="image/png",
            case_id="case-hyb-06",
            document_id="doc-hyb-06",
            processing_run_id="run-hyb-06",
            document_sha256="6" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED
        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["engine_name"] == "rapidocr-onnxruntime"
        assert page_obs.evidence_payload["routing_decision"] == "DIRECT_IMAGE_OPTICAL_OCR"
