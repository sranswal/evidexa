"""Unit tests for RapidOcrAdapter: scanned text recognition, coordinates, and edge cases."""

from pathlib import Path
from unittest.mock import patch

from document_intelligence.domain.enums import CoordinateSystem, PipelineStatus
from document_intelligence.modules.forensics.adapters.ocr.rapidocr_adapter import RapidOcrAdapter
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from tests.fixtures.ocr_factory import (
    create_blank_page_pdf,
    create_image_based_table_pdf,
    create_multilingual_pdf,
    create_noisy_skewed_scan_pdf,
    create_rotated_pages_pdf,
    create_scanned_multipage_pdf,
    create_scanned_printed_text_pdf,
)


class TestRapidOcrAdapter:
    """Verifies optical character recognition, coordinate normalization, and limits on RapidOCR."""

    def test_scanned_printed_text_recognized_with_high_confidence(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "scanned_statement.pdf"
        create_scanned_printed_text_pdf(pdf_path)

        adapter = RapidOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            detected_media_type="application/pdf",
            case_id="case-rapid-01",
            document_id="doc-rapid-01",
            processing_run_id="run-rapid-01",
            document_sha256="a" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED
        assert len(output.observations) >= 2

        # Verify text was recognized on page 1
        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["token_count"] > 10
        assert page_obs.evidence_payload["has_vector_text"] is False
        assert page_obs.evidence_payload["engine_name"] == "rapidocr-onnxruntime"

        # Check recognized keywords
        sample = page_obs.evidence_payload["text_sample"].upper()
        assert "STATEMENT" in sample or "ACCOUNT" in sample or "TRANSACTION" in sample

    def test_scanned_multipage_sequential_processing(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "multipage_scan.pdf"
        create_scanned_multipage_pdf(pdf_path)

        adapter = RapidOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-rapid-02",
            document_id="doc-rapid-02",
            processing_run_id="run-rapid-02",
            document_sha256="b" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = [o for o in output.observations if o.observation_type == "ocr_page"]
        assert len(page_obs) == 2
        assert page_obs[0].page_number == 1
        assert page_obs[1].page_number == 2

    def test_rotated_scanned_pages_orientation_handled(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "rotated.pdf"
        create_rotated_pages_pdf(pdf_path)

        adapter = RapidOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-rapid-03",
            document_id="doc-rapid-03",
            processing_run_id="run-rapid-03",
            document_sha256="c" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = [o for o in output.observations if o.observation_type == "ocr_page"]
        assert len(page_obs) == 4
        # All 4 orientations recognized text
        for po in page_obs:
            assert po.evidence_payload["token_count"] > 0

    def test_low_res_and_noisy_skewed_scan_robustness(self, tmp_path: Path) -> None:
        noisy_pdf = tmp_path / "noisy_skewed.pdf"
        create_noisy_skewed_scan_pdf(noisy_pdf)

        adapter = RapidOcrAdapter()
        input_data = AnalyzerInput(
            file_path=noisy_pdf,
            declared_media_type="application/pdf",
            case_id="case-rapid-04",
            document_id="doc-rapid-04",
            processing_run_id="run-rapid-04",
            document_sha256="d" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED
        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["token_count"] >= 3

    def test_image_based_table_recognition(self, tmp_path: Path) -> None:
        table_pdf = tmp_path / "image_table.pdf"
        create_image_based_table_pdf(table_pdf)

        adapter = RapidOcrAdapter()
        input_data = AnalyzerInput(
            file_path=table_pdf,
            declared_media_type="application/pdf",
            case_id="case-rapid-05",
            document_id="doc-rapid-05",
            processing_run_id="run-rapid-05",
            document_sha256="e" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED
        table_obs = [o for o in output.observations if o.observation_type == "ocr_table"]
        assert len(table_obs) >= 1
        assert table_obs[0].coordinate_system == CoordinateSystem.NORMALIZED_0_1

    def test_multilingual_scan_handles_latin_components(self, tmp_path: Path) -> None:
        multi_pdf = tmp_path / "multilingual.pdf"
        create_multilingual_pdf(multi_pdf)

        adapter = RapidOcrAdapter()
        input_data = AnalyzerInput(
            file_path=multi_pdf,
            declared_media_type="application/pdf",
            case_id="case-rapid-06",
            document_id="doc-rapid-06",
            processing_run_id="run-rapid-06",
            document_sha256="f" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED
        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["token_count"] >= 5
        sample = page_obs.evidence_payload["text_sample"].upper()
        assert "MULTILINGUAL" in sample or "STANDARD" in sample or "IFSC" in sample

    def test_blank_page_returns_no_text_detected(self, tmp_path: Path) -> None:
        blank_pdf = tmp_path / "blank.pdf"
        create_blank_page_pdf(blank_pdf)

        adapter = RapidOcrAdapter()
        input_data = AnalyzerInput(
            file_path=blank_pdf,
            declared_media_type="application/pdf",
            case_id="case-rapid-07",
            document_id="doc-rapid-07",
            processing_run_id="run-rapid-07",
            document_sha256="0" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED
        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["extraction_status"] == "NO_TEXT_DETECTED"
        assert page_obs.evidence_payload["token_count"] == 0

    def test_coordinate_normalization_invariants(self, tmp_path: Path) -> None:
        scan_pdf = tmp_path / "scan.pdf"
        create_scanned_printed_text_pdf(scan_pdf)

        adapter = RapidOcrAdapter()
        doc = adapter._extract_document(
            file_path=scan_pdf,
            media_type="application/pdf",
            case_id="c",
            document_id="d",
            processing_run_id="r",
        )

        assert len(doc.pages) == 1
        page = doc.pages[0]
        assert len(page.tokens) > 5

        for token in page.tokens:
            box = token.bounding_box
            assert box is not None
            assert 0.0 <= box.x <= 1.0
            assert 0.0 <= box.y <= 1.0
            assert 0.0 <= box.width <= 1.0
            assert 0.0 <= box.height <= 1.0
            assert box.x + box.width <= 1.0001
            assert box.y + box.height <= 1.0001
            # Honest uncalibrated confidence preserved
            assert token.confidence is not None
            assert 0.0 <= token.confidence <= 1.0

    def test_missing_file_fails_safely(self, tmp_path: Path) -> None:
        adapter = RapidOcrAdapter()
        missing = tmp_path / "nonexistent.pdf"
        input_data = AnalyzerInput(
            file_path=missing,
            declared_media_type="application/pdf",
            case_id="case-err",
            document_id="doc-err",
            processing_run_id="run-err",
            document_sha256="2" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.FAILED
        assert len(output.errors) >= 1

    def test_engine_initialization_failure_handled_safely(self, tmp_path: Path) -> None:
        adapter = RapidOcrAdapter()
        pdf_path = tmp_path / "sample.pdf"
        create_scanned_printed_text_pdf(pdf_path)

        input_data = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-init-err",
            document_id="doc-init-err",
            processing_run_id="run-init-err",
            document_sha256="3" * 64,
        )

        with patch.object(
            adapter, "_get_engine", side_effect=RuntimeError("Simulated ONNX init failure")
        ):
            output = adapter.analyze(input_data)
            assert output.status == PipelineStatus.FAILED
            assert "Simulated ONNX init failure" in output.errors[0]
