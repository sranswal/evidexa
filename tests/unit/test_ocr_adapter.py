"""Unit tests for PdfiumOcrAdapter: extraction accuracy, rotations, tables, and limits."""

from pathlib import Path

from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.modules.forensics.adapters.ocr.pdfium_adapter import PdfiumOcrAdapter
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from tests.fixtures.ocr_factory import (
    create_clean_digital_pdf,
    create_multi_column_pdf,
    create_multilingual_pdf,
    create_rotated_pages_pdf,
    create_scanned_printed_text_pdf,
    create_table_pdf,
)


class TestPdfiumOcrAdapter:
    """Tests for PdfiumOcrAdapter core extraction capabilities."""

    def test_adapter_metadata_and_analyzer_contract(self) -> None:
        adapter = PdfiumOcrAdapter()
        assert adapter.analyzer_id == "pdfium-ocr-engine"
        assert adapter.version == "1.0.0"
        assert "application/pdf" in adapter.supported_media_types
        assert "image/png" in adapter.supported_media_types
        assert adapter.can_analyze("application/pdf") is True
        assert adapter.can_analyze("image/png") is True
        assert adapter.can_analyze("video/mp4") is False

    def test_clean_digital_pdf_token_and_line_extraction(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "clean_digital.pdf"
        create_clean_digital_pdf(pdf_path)

        adapter = PdfiumOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case-101",
            document_id="doc-101",
            processing_run_id="run-101",
            document_sha256="a" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED
        assert len(output.observations) >= 1
        assert len(output.errors) == 0

        # Check document text observations
        doc_obs = [o for o in output.observations if o.observation_type == "ocr_text"]
        assert len(doc_obs) == 1
        assert doc_obs[0].evidence_payload["total_tokens"] > 30
        assert "ACME AUDIT" in doc_obs[0].evidence_payload["text_preview"]

    def test_scanned_printed_pdf_detects_raster_status(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "scanned_doc.pdf"
        create_scanned_printed_text_pdf(pdf_path)

        adapter = PdfiumOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case-102",
            document_id="doc-102",
            processing_run_id="run-102",
            document_sha256="b" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        page_obs = [o for o in output.observations if o.observation_type == "ocr_page"]
        assert len(page_obs) == 1
        assert page_obs[0].evidence_payload["has_vector_text"] is False
        assert page_obs[0].evidence_payload["extraction_status"] == "SCANNED_PAGE_DETECTED"

    def test_rotated_pages_coordinate_mapping(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "rotated.pdf"
        create_rotated_pages_pdf(pdf_path)

        adapter = PdfiumOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case-103",
            document_id="doc-103",
            processing_run_id="run-103",
            document_sha256="c" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        # 4 pages must be extracted
        page_obs = [o for o in output.observations if o.observation_type == "ocr_page"]
        assert len(page_obs) == 4

    def test_table_pdf_extracts_grid_and_cells(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "table.pdf"
        create_table_pdf(pdf_path)

        adapter = PdfiumOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case-104",
            document_id="doc-104",
            processing_run_id="run-104",
            document_sha256="d" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        table_obs = [o for o in output.observations if o.observation_type == "ocr_table"]
        assert len(table_obs) >= 1
        tbl = table_obs[0]
        assert tbl.evidence_payload["num_rows"] >= 4
        assert tbl.evidence_payload["num_cols"] >= 3
        assert tbl.bounding_box is not None

    def test_multi_column_layout_reading_order(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "multi_col.pdf"
        create_multi_column_pdf(pdf_path)

        adapter = PdfiumOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case-105",
            document_id="doc-105",
            processing_run_id="run-105",
            document_sha256="e" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED

        doc_obs = [o for o in output.observations if o.observation_type == "ocr_text"][0]
        preview = doc_obs.evidence_payload["text_preview"]
        assert "EXECUTIVE SUMMARY" in preview

    def test_multilingual_document_token_extraction(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "multilingual.pdf"
        create_multilingual_pdf(pdf_path)

        adapter = PdfiumOcrAdapter()
        input_data = AnalyzerInput(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case-106",
            document_id="doc-106",
            processing_run_id="run-106",
            document_sha256="f" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.SUCCEEDED
        assert any("SBIN0001234" in str(o.evidence_payload) for o in output.observations)

    def test_oversized_page_count_raises_error(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "oversized.pdf"
        create_rotated_pages_pdf(pdf_path)  # Has 4 pages

        # Configure adapter with max_pages = 2
        adapter = PdfiumOcrAdapter(max_pages=2)
        input_data = AnalyzerInput(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case-107",
            document_id="doc-107",
            processing_run_id="run-107",
            document_sha256="0" * 64,
        )

        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.FAILED
        assert any("exceeds maximum permitted limit" in err for err in output.errors)

    def test_nonexistent_file_fails_safely(self, tmp_path: Path) -> None:
        adapter = PdfiumOcrAdapter()
        input_data = AnalyzerInput(
            file_path=tmp_path / "does_not_exist.pdf",
            media_type="application/pdf",
            case_id="case-108",
            document_id="doc-108",
            processing_run_id="run-108",
            document_sha256="1" * 64,
        )
        output = adapter.analyze(input_data)
        assert output.status == PipelineStatus.FAILED
        assert len(output.errors) >= 1
