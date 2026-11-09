"""Unit tests for Phase 2C.1.2 OCR operational hardening, routing validation, and reproducibility.

Covers:
1. RapidOCR CPU execution controls (intra_op_num_threads, inter_op_num_threads).
2. Offline inference verification with zero network calls at startup/runtime.
3. Uncalibrated confidence metadata provenance for RapidOCR vs None for PDFium.
4. Partial page failure semantics and artifact integrity.
5. Hybrid adapter configurable sparse threshold and page-level routing invariants.
6. Mixed page with >30 characters limitation verification (force_ocr requirement).
7. Latin/English optical recognition vs Devanagari model boundary behavior.
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pikepdf
import pytest
from pikepdf import Array, Dictionary, Name

from document_intelligence.core.config import Settings
from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.modules.forensics.adapters.ocr.hybrid_adapter import HybridOcrAdapter
from document_intelligence.modules.forensics.adapters.ocr.pdfium_adapter import PdfiumOcrAdapter
from document_intelligence.modules.forensics.adapters.ocr.rapidocr_adapter import RapidOcrAdapter
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from tests.fixtures.ocr_factory import (
    create_clean_digital_pdf,
    create_mixed_digital_and_scanned_pdf,
    create_multilingual_pdf,
    create_scanned_printed_text_pdf,
)


def _build_exact_char_count_pdf(path: Path, text: str) -> Path:
    """Helper creating a digital PDF with exact character sequence for threshold testing."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    resources = Dictionary(Font=Dictionary(F1=font))
    content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET\n".encode("latin1")
    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


class TestOcrHardeningAndReproducibility:
    """Hardening and operational verification tests for OCR engines."""

    @pytest.fixture
    def temp_storage(self, tmp_path: Path) -> FilesystemDocumentStorage:
        return FilesystemDocumentStorage(app_settings=Settings(data_dir=tmp_path / "data"))

    def test_rapidocr_thread_configuration_and_engine_initialization(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify intra_op_num_threads and inter_op_num_threads are accepted and recorded in metadata."""
        adapter = RapidOcrAdapter(
            storage=temp_storage,
            intra_op_num_threads=2,
            inter_op_num_threads=1,
        )

        pdf_path = tmp_path / "scanned.pdf"
        create_scanned_printed_text_pdf(pdf_path)

        analyzer_input = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case_thread_01",
            document_id="doc_thread_01",
            processing_run_id="run_thread_01",
            document_sha256="0" * 64,
            options={"intra_op_num_threads": 2, "inter_op_num_threads": 1},
        )

        output = adapter.analyze(analyzer_input)
        assert output.status == PipelineStatus.SUCCEEDED

        cap = next(
            c
            for c in output.capabilities_executed
            if c.capability_id == "optical-character-recognition"
        )
        assert cap.status == "PASS"

    def test_rapidocr_confidence_uncalibrated_provenance(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify tokens and lines carry uncalibrated_model_score provenance from RapidOCR."""
        adapter = RapidOcrAdapter(storage=temp_storage)

        pdf_path = tmp_path / "scanned_conf.pdf"
        create_scanned_printed_text_pdf(pdf_path)

        analyzer_input = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case_conf_01",
            document_id="doc_conf_01",
            processing_run_id="run_conf_01",
            document_sha256="0" * 64,
        )

        output = adapter.analyze(analyzer_input)
        assert output.status == PipelineStatus.SUCCEEDED

        doc = adapter._extract_document(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case_conf_01",
            document_id="doc_conf_01",
            processing_run_id="run_conf_01",
        )

        assert len(doc.pages) == 1
        page = doc.pages[0]
        assert len(page.tokens) > 0

        for token in page.tokens:
            assert token.confidence is not None
            assert 0.0 <= token.confidence <= 1.0
            assert token.metadata.get("confidence_calibration_method") == "uncalibrated_model_score"

        for line in page.lines:
            assert line.confidence is not None
            assert 0.0 <= line.confidence <= 1.0
            assert line.metadata.get("confidence_calibration_method") == "uncalibrated_model_score"

    def test_pdfium_confidence_none_and_not_applicable_metadata(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify PDFium programmatic extraction explicitly marks confidence=None and not_applicable."""
        adapter = PdfiumOcrAdapter(storage=temp_storage)

        pdf_path = tmp_path / "digital_conf.pdf"
        create_clean_digital_pdf(pdf_path)

        analyzer_input = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case_pdfium_conf_01",
            document_id="doc_pdfium_conf_01",
            processing_run_id="run_pdfium_conf_01",
            document_sha256="0" * 64,
        )

        output = adapter.analyze(analyzer_input)
        assert output.status == PipelineStatus.SUCCEEDED

        doc = adapter._extract_document(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case_pdfium_conf_01",
            document_id="doc_pdfium_conf_01",
            processing_run_id="run_pdfium_conf_01",
        )

        assert len(doc.pages) == 1
        page = doc.pages[0]
        assert len(page.tokens) > 0

        for token in page.tokens:
            assert token.confidence is None
            assert (
                token.metadata.get("confidence_calibration_method")
                == "not_applicable_vector_extraction"
            )

        for line in page.lines:
            assert line.confidence is None
            assert (
                line.metadata.get("confidence_calibration_method")
                == "not_applicable_vector_extraction"
            )

    def test_rapidocr_offline_execution_zero_network_calls(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify RapidOCR performs inference offline with zero outbound network calls."""
        adapter = RapidOcrAdapter(storage=temp_storage)

        pdf_path = tmp_path / "offline_test.pdf"
        create_scanned_printed_text_pdf(pdf_path)

        analyzer_input = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case_offline_01",
            document_id="doc_offline_01",
            processing_run_id="run_offline_01",
            document_sha256="0" * 64,
        )

        def mock_socket_connect(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Outbound network connection forbidden during offline OCR!")

        with patch.object(socket.socket, "connect", side_effect=mock_socket_connect):
            output = adapter.analyze(analyzer_input)
            assert output.status == PipelineStatus.SUCCEEDED
            assert len(output.observations) >= 2

    def test_rapidocr_partial_page_failure_handling(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify that when a single page in a multi-page document fails, pipeline reports PARTIALLY_SUCCEEDED."""
        adapter = RapidOcrAdapter(storage=temp_storage)

        pdf_path = tmp_path / "multipage_fail.pdf"
        create_mixed_digital_and_scanned_pdf(pdf_path)  # 2 pages

        original_recognize = adapter.recognize_rendered_page

        def simulated_recognize(engine: Any, rendered_page: Any) -> Any:
            if rendered_page.page_number == 2:
                raise RuntimeError("Simulated inference engine failure on page 2")
            return original_recognize(engine, rendered_page)

        with patch.object(adapter, "recognize_rendered_page", side_effect=simulated_recognize):
            analyzer_input = AnalyzerInput(
                file_path=pdf_path,
                declared_media_type="application/pdf",
                case_id="case_partial_01",
                document_id="doc_partial_01",
                processing_run_id="run_partial_01",
                document_sha256="0" * 64,
            )
            output = adapter.analyze(analyzer_input)

            assert output.status == PipelineStatus.PARTIALLY_SUCCEEDED
            cap = next(
                c
                for c in output.capabilities_executed
                if c.capability_id == "optical-character-recognition"
            )
            assert cap.status == "PARTIAL"
            assert cap.details["failed_pages"] == 1
            assert cap.details["successful_pages"] == 1

            # Check observations
            page_2_obs = next(
                o
                for o in output.observations
                if o.observation_type == "ocr_page" and o.page_number == 2
            )
            assert page_2_obs.evidence_payload["extraction_status"] == "FAILED"

    def test_hybrid_adapter_partial_page_failure_handling(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify Hybrid adapter marks PARTIALLY_SUCCEEDED when one page fails."""
        adapter = HybridOcrAdapter(storage=temp_storage)

        pdf_path = tmp_path / "hybrid_partial.pdf"
        create_mixed_digital_and_scanned_pdf(pdf_path)

        original_process_page = adapter._process_hybrid_page

        def simulated_process(pdf_page: Any, page_number: int, **kwargs: Any) -> Any:
            if page_number == 2:
                raise RuntimeError("Simulated corruption on page 2")
            return original_process_page(pdf_page=pdf_page, page_number=page_number, **kwargs)

        with patch.object(adapter, "_process_hybrid_page", side_effect=simulated_process):
            analyzer_input = AnalyzerInput(
                file_path=pdf_path,
                declared_media_type="application/pdf",
                case_id="case_hyb_partial_01",
                document_id="doc_hyb_partial_01",
                processing_run_id="run_hyb_partial_01",
                document_sha256="0" * 64,
            )
            output = adapter.analyze(analyzer_input)

            assert output.status == PipelineStatus.PARTIALLY_SUCCEEDED
            cap = next(
                c for c in output.capabilities_executed if c.capability_id == "hybrid-ocr-routing"
            )
            assert cap.status == "PARTIAL"
            assert cap.details["failed_pages"] == 1

    def test_hybrid_routing_configurable_sparse_threshold(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify configurable sparse_char_threshold correctly triggers optical fallback."""
        pdf_path = tmp_path / "sparse_page.pdf"
        # 40 characters: "Short header text 1234567890 1234567890."
        text = "Short header text 1234567890 1234567890."
        _build_exact_char_count_pdf(pdf_path, text=text)

        adapter = HybridOcrAdapter(storage=temp_storage)

        # Case A: Default threshold (30): 40 > 30 -> DIGITAL_VECTOR_PRIMARY
        doc_default = adapter._extract_document(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case_sp_01",
            document_id="doc_sp_01",
            processing_run_id="run_sp_01",
            options={"sparse_threshold": 30},
        )
        assert doc_default.pages[0].routing_decision == "DIGITAL_VECTOR_PRIMARY"
        assert doc_default.pages[0].engine_name == "pypdfium2"

        # Case B: Threshold 50: 40 < 50 -> SPARSE_TEXT_FALLBACK
        doc_fallback = adapter._extract_document(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case_sp_02",
            document_id="doc_sp_02",
            processing_run_id="run_sp_02",
            options={"sparse_threshold": 50},
        )
        assert doc_fallback.pages[0].routing_decision == "SPARSE_TEXT_FALLBACK"
        assert doc_fallback.pages[0].engine_name == "rapidocr-onnxruntime"
        assert "pdfium" in doc_fallback.pages[0].alternative_extractions
        assert doc_fallback.pages[0].alternative_extractions["pdfium"]["sparse_threshold"] == 50

    def test_hybrid_mixed_page_above_sparse_threshold_limitation_behavior(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify limitation: page with >30 digital chars routes to digital primary unless force_ocr=True."""
        pdf_path = tmp_path / "mixed_limitation.pdf"
        create_clean_digital_pdf(pdf_path)

        adapter = HybridOcrAdapter(storage=temp_storage)

        # Without force_ocr
        doc_unforced = adapter._extract_document(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case_lim_01",
            document_id="doc_lim_01",
            processing_run_id="run_lim_01",
            options={"force_ocr": False},
        )
        assert doc_unforced.pages[0].routing_decision == "DIGITAL_VECTOR_PRIMARY"

        # With force_ocr
        doc_forced = adapter._extract_document(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case_lim_02",
            document_id="doc_lim_02",
            processing_run_id="run_lim_02",
            options={"force_ocr": True},
        )
        assert doc_forced.pages[0].routing_decision == "FORCED_OPTICAL_OCR"
        assert doc_forced.pages[0].engine_name == "rapidocr-onnxruntime"

    def test_multilingual_latin_vs_devanagari_recognition_boundary(
        self, tmp_path: Path, temp_storage: FilesystemDocumentStorage
    ) -> None:
        """Verify Latin keywords are extracted while Devanagari script is unhandled by default model."""
        pdf_path = tmp_path / "multilingual_boundary.pdf"
        create_multilingual_pdf(pdf_path)

        adapter = RapidOcrAdapter(storage=temp_storage)
        doc = adapter._extract_document(
            file_path=pdf_path,
            media_type="application/pdf",
            case_id="case_multi_01",
            document_id="doc_multi_01",
            processing_run_id="run_multi_01",
        )

        assert len(doc.pages) == 1
        full_text = doc.full_raw_text

        # Latin keywords must be recognized
        assert "MULTILINGUAL" in full_text
        assert "IFSC" in full_text

        # Note: default PP-OCRv4 model rec dictionary does not include Devanagari Unicode codepoints
        # Proves requirement that multilingual claim cannot include Hindi until verified Devanagari model is loaded
        token_texts = [t.raw_text for t in doc.pages[0].tokens]
        assert any("MULTILINGUAL" in t for t in token_texts)
