"""Unit and integration tests for DevanagariRapidOcrAdapter and OcrModelArtifactManager.

Covers cryptographic verification, error handling, thread safety, Hindi recognition,
numeral conversion, coordinate normalization, provenance metadata, and regression safety.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from document_intelligence.core.config import settings
from document_intelligence.domain.enums import (
    CoordinateSystem,
    PageRoutingDecision,
    PipelineStatus,
    ScriptType,
)
from document_intelligence.domain.models.bounding_box import PageGeometry
from document_intelligence.modules.forensics.adapters.ocr.artifact_manager import (
    PP_OCRV5_DEVANAGARI,
    ApprovedModelArtifact,
    ModelArtifactCorruptError,
    ModelArtifactNotFoundError,
    OcrModelArtifactManager,
)
from document_intelligence.modules.forensics.adapters.ocr.devanagari_adapter import (
    MAX_PIXEL_DIMENSION,
    DevanagariRapidOcrAdapter,
)
from document_intelligence.modules.forensics.adapters.ocr.rapidocr_adapter import RapidOcrAdapter
from document_intelligence.modules.forensics.adapters.visual.page_renderer import RenderedPage
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from tests.fixtures.ocr_factory import create_scanned_printed_text_pdf


class TestArtifactManager:
    """Tests 1-4: Cryptographic verification of model and dictionary artifacts."""

    def test_artifact_manager_correct_hash_verification(self) -> None:
        """Test 1: Verify correct model and dictionary SHA-256 hashes."""
        manager = OcrModelArtifactManager(models_dir=settings.ocr_model_dir)
        verified = manager.verify_artifact(PP_OCRV5_DEVANAGARI)

        assert verified.model_filename == "devanagari_PP-OCRv5_mobile_rec_infer.onnx"
        assert verified.dictionary_filename == "devanagari_v5_dict.txt"
        assert verified.model_sha256 == PP_OCRV5_DEVANAGARI.model_sha256
        assert verified.dictionary_sha256 == PP_OCRV5_DEVANAGARI.dictionary_sha256
        assert verified.model_path.exists()
        assert verified.dictionary_path.exists()

    def test_artifact_manager_missing_model_file(self, tmp_path: Path) -> None:
        """Test 2: Missing model artifact raises ModelArtifactNotFoundError."""
        manager = OcrModelArtifactManager(models_dir=tmp_path / "nonexistent")
        with pytest.raises(ModelArtifactNotFoundError) as exc_info:
            manager.verify_artifact(PP_OCRV5_DEVANAGARI)
        assert "not found" in str(exc_info.value).lower()

    def test_artifact_manager_corrupted_model_file(self, tmp_path: Path) -> None:
        """Test 3: Corrupted model file raises ModelArtifactCorruptError."""
        # Create invalid model file but valid-looking dict file
        model_file = tmp_path / PP_OCRV5_DEVANAGARI.model_filename
        model_file.write_bytes(b"corrupted model contents")
        dict_file = tmp_path / PP_OCRV5_DEVANAGARI.dictionary_filename
        dict_file.write_bytes(b"some dict")

        manager = OcrModelArtifactManager(models_dir=tmp_path)
        with pytest.raises(ModelArtifactCorruptError) as exc_info:
            manager.verify_artifact(PP_OCRV5_DEVANAGARI)
        assert "hash mismatch" in str(exc_info.value).lower()

    def test_artifact_manager_incorrect_dict_checksum(self, tmp_path: Path) -> None:
        """Test 4: Corrupted dictionary raises ModelArtifactCorruptError."""
        # Copy real model file
        real_model = settings.ocr_model_dir / PP_OCRV5_DEVANAGARI.model_filename
        model_file = tmp_path / PP_OCRV5_DEVANAGARI.model_filename
        model_file.write_bytes(real_model.read_bytes())

        # Corrupt dictionary
        dict_file = tmp_path / PP_OCRV5_DEVANAGARI.dictionary_filename
        dict_file.write_bytes(b"invalid dictionary text")

        manager = OcrModelArtifactManager(models_dir=tmp_path)
        with pytest.raises(ModelArtifactCorruptError) as exc_info:
            manager.verify_artifact(PP_OCRV5_DEVANAGARI)
        assert "hash mismatch" in str(exc_info.value).lower()


class TestDevanagariEngineConfiguration:
    """Tests 5-8: Engine initialization, parameter invariants, and threshold enforcement."""

    def test_devanagari_engine_initialization_success(self) -> None:
        """Test 5: Successful PP-OCRv5 engine initialization."""
        adapter = DevanagariRapidOcrAdapter()
        engine = adapter._get_engine()
        assert engine is not None
        # Verify subsequent call returns cached engine
        assert adapter._get_engine() is engine

    def test_devanagari_engine_invalid_model_config(self, tmp_path: Path) -> None:
        """Test 6: Invalid model artifact config raises error."""
        invalid_artifact = ApprovedModelArtifact(
            model_id="invalid-engine",
            model_version="1.0.0",
            model_filename="missing.onnx",
            expected_model_sha256="0" * 64,
            dictionary_filename="missing_dict.txt",
            expected_dictionary_sha256="1" * 64,
            upstream_source="test",
            upstream_revision="test",
            license_evidence="Apache-2.0",
            rec_img_shape=[3, 48, 320],
            default_use_cls=False,
            default_unclip_ratio=1.6,
            default_box_thresh=0.3,
        )
        adapter = DevanagariRapidOcrAdapter(
            artifact_manager=OcrModelArtifactManager(models_dir=tmp_path),
            model_artifact=invalid_artifact,
        )
        with pytest.raises(ModelArtifactNotFoundError):
            adapter._get_engine()

    def test_devanagari_engine_explicit_use_cls_false(self) -> None:
        """Test 7: use_cls=False is strictly enforced."""
        adapter = DevanagariRapidOcrAdapter()
        assert adapter.use_cls is False
        with patch("rapidocr_onnxruntime.RapidOCR") as mock_rapid:
            adapter._engine = None
            adapter._get_engine()
            mock_rapid.assert_called_once()
            _, kwargs = mock_rapid.call_args
            assert kwargs.get("use_cls") is False

    def test_devanagari_engine_configured_detection_thresholds(self) -> None:
        """Test 8: box_thresh=0.3, unclip_ratio=1.6, and rec_img_shape=[3, 48, 320] are set."""
        adapter = DevanagariRapidOcrAdapter()
        assert adapter.box_thresh == 0.3
        assert adapter.unclip_ratio == 1.6
        assert adapter.rec_img_shape == [3, 48, 320]

        with patch("rapidocr_onnxruntime.RapidOCR") as mock_rapid:
            adapter._engine = None
            adapter._get_engine()
            mock_rapid.assert_called_once()
            _, kwargs = mock_rapid.call_args
            assert kwargs.get("box_thresh") == 0.3
            assert kwargs.get("unclip_ratio") == 1.6
            assert kwargs.get("rec_img_shape") == [3, 48, 320]


class TestDevanagariOcrInference:
    """Tests 9-16: Multilingual recognition, numeral conversion, coordinates, and metadata."""

    def _make_dummy_rendered_page(
        self, width: int = 1000, height: int = 1000, page_num: int = 1
    ) -> RenderedPage:
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        geom = PageGeometry(
            page_number=page_num,
            width=float(width),
            height=float(height),
            dpi=150.0,
            rotation_applied=0,
            original_rotation=0,
        )
        return RenderedPage(
            page_number=page_num,
            image=img,
            geometry=geom,
            pixel_width=width,
            pixel_height=height,
        )

    def test_hindi_ocr_output_recognition(self) -> None:
        """Test 9: Hindi text recognized with Devanagari script classification."""
        adapter = DevanagariRapidOcrAdapter()
        rendered_page = self._make_dummy_rendered_page()

        mock_result = [
            (
                [[100, 100], [240, 100], [240, 150], [100, 150]],
                "खाता",
                0.9500,
            ),
            (
                [[250, 100], [400, 100], [400, 150], [250, 150]],
                "विवरण",
                0.9400,
            ),
        ]
        mock_engine = MagicMock(return_value=(mock_result, 0.05))

        page = adapter.recognize_rendered_page(mock_engine, rendered_page)

        assert page.extraction_status == "SUCCEEDED"
        assert len(page.tokens) == 2
        assert page.tokens[0].raw_text == "खाता"
        assert page.tokens[0].detected_script == ScriptType.DEVANAGARI
        assert page.tokens[1].raw_text == "विवरण"
        assert page.tokens[1].detected_script == ScriptType.DEVANAGARI
        assert "खाता" in page.raw_text
        assert "विवरण" in page.raw_text
        assert page.script_distribution.get("DEVANAGARI") == 1.0

    def test_english_ocr_regression_baseline(self, tmp_path: Path) -> None:
        """Test 10: Existing RapidOcrAdapter baseline remains fully operational."""
        pdf_path = tmp_path / "baseline_scan.pdf"
        create_scanned_printed_text_pdf(pdf_path)

        adapter = RapidOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-reg-01",
            document_id="doc-reg-01",
            processing_run_id="run-reg-01",
            document_sha256="c" * 64,
        )
        output = adapter.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED
        assert output.analyzer_id == "rapidocr-optical-engine"
        assert len(output.observations) >= 2

    def test_mixed_hindi_english_text_output(self) -> None:
        """Test 11: Mixed Hindi and English tokens correctly segregated by script."""
        adapter = DevanagariRapidOcrAdapter()
        rendered_page = self._make_dummy_rendered_page()

        mock_result = [
            (
                [[50, 50], [200, 50], [200, 90], [50, 90]],
                "STATE BANK",
                0.9320,
            ),
            (
                [[210, 50], [380, 50], [380, 90], [210, 90]],
                "भारतीय स्टेट बैंक",
                0.9450,
            ),
        ]
        mock_engine = MagicMock(return_value=(mock_result, 0.04))

        page = adapter.recognize_rendered_page(mock_engine, rendered_page)

        scripts = [t.detected_script for t in page.tokens]
        assert ScriptType.LATIN in scripts
        assert ScriptType.DEVANAGARI in scripts
        assert "LATIN" in page.script_distribution
        assert "DEVANAGARI" in page.script_distribution

    def test_devanagari_numeral_conversion(self) -> None:
        """Test 12: Devanagari numeral conversion preserves original in raw_text and converts in normalized_text."""
        adapter = DevanagariRapidOcrAdapter()
        rendered_page = self._make_dummy_rendered_page()

        mock_result = [
            (
                [[50, 50], [150, 50], [150, 90], [50, 90]],
                "रकम",
                0.9200,
            ),
            (
                [[160, 50], [260, 50], [260, 90], [160, 90]],
                "१२५०००",
                0.9600,
            ),
            (
                [[270, 50], [370, 50], [370, 90], [270, 90]],
                "रुपये",
                0.9100,
            ),
        ]
        mock_engine = MagicMock(return_value=(mock_result, 0.03))

        page = adapter.recognize_rendered_page(mock_engine, rendered_page)
        num_tok = next(t for t in page.tokens if t.raw_text == "१२५०००")

        assert num_tok.is_numeral_converted is True
        assert num_tok.original_numeral_system == "DEVANAGARI"
        assert num_tok.original_raw_value == "१२५०००"
        assert num_tok.raw_text == "१२५०००"
        assert num_tok.normalized_text == "125000"

    def test_bounding_box_coordinate_conversion(self) -> None:
        """Test 13: 4-point polygon mapped to canonical [0, 1] normalized bounding box."""
        adapter = DevanagariRapidOcrAdapter()
        rendered_page = self._make_dummy_rendered_page(width=1000, height=2000)

        # Polygon from (100, 200) to (500, 400)
        mock_result = [
            (
                [[100, 200], [500, 200], [500, 400], [100, 400]],
                "नमूना",
                0.9500,
            )
        ]
        mock_engine = MagicMock(return_value=(mock_result, 0.02))

        page = adapter.recognize_rendered_page(mock_engine, rendered_page)
        box = page.tokens[0].bounding_box

        assert box.coordinate_system == CoordinateSystem.NORMALIZED_0_1
        assert box.x == 0.1  # 100 / 1000
        assert box.y == 0.1  # 200 / 2000
        assert box.width == 0.4  # (500 - 100) / 1000
        assert box.height == 0.1  # (400 - 200) / 2000

    def test_missing_or_empty_ocr_output(self) -> None:
        """Test 14: Empty OCR result handled gracefully as NO_TEXT_DETECTED."""
        adapter = DevanagariRapidOcrAdapter()
        rendered_page = self._make_dummy_rendered_page()

        mock_engine = MagicMock(return_value=(None, 0.01))

        page = adapter.recognize_rendered_page(mock_engine, rendered_page)
        assert page.extraction_status == "NO_TEXT_DETECTED"
        assert len(page.tokens) == 0
        assert len(page.lines) == 0
        assert page.raw_text == ""
        assert page.routing_decision == PageRoutingDecision.OPTICAL_OCR

    def test_raw_text_preservation_unmutated(self) -> None:
        """Test 15: Raw text retains exact original characters."""
        adapter = DevanagariRapidOcrAdapter()
        rendered_page = self._make_dummy_rendered_page()

        raw_str = "दिनांक: ०१/०४/२०२६"
        mock_result = [
            (
                [[50, 50], [300, 50], [300, 90], [50, 90]],
                raw_str,
                0.9200,
            )
        ]
        mock_engine = MagicMock(return_value=(mock_result, 0.02))

        page = adapter.recognize_rendered_page(mock_engine, rendered_page)
        assert page.lines[0].raw_text == raw_str
        assert "०१/०४/२०२६" in page.raw_text

    def test_metadata_and_provenance_population(self, tmp_path: Path) -> None:
        """Test 16: OcrEngineMetadata populated with scrubbed paths and cryptographic hashes."""
        img_file = tmp_path / "test_doc.png"
        img = Image.new("RGB", (400, 200), color=(255, 255, 255))
        img.save(img_file)

        adapter = DevanagariRapidOcrAdapter()
        with patch.object(adapter, "_get_engine") as mock_get_eng:
            mock_eng = MagicMock(return_value=(None, 0.01))
            mock_get_eng.return_value = mock_eng

            doc = adapter._extract_document(
                file_path=img_file,
                media_type="image/png",
                case_id="case-prov-01",
                document_id="doc-prov-01",
                processing_run_id="run-prov-01",
            )

        meta = doc.engine_metadata
        assert meta is not None
        assert meta.engine_name == "RapidOCR PP-OCRv5 Devanagari"
        assert meta.engine_version == "2.0.0"
        assert meta.character_dict_name == "devanagari_v5_dict.txt"
        assert meta.model_id == "devanagari_PP-OCRv5_mobile_rec_infer.onnx"
        assert meta.runtime_name == "ONNXRuntime-CPU"
        assert meta.model_artifacts["rec_model"] == PP_OCRV5_DEVANAGARI.model_sha256
        assert meta.model_artifacts["rec_dict"] == PP_OCRV5_DEVANAGARI.dictionary_sha256
        # Assert no host absolute directory paths leaked
        for path_val in meta.model_artifacts.values():
            assert "C:\\" not in path_val
            assert "/home" not in path_val


class TestConcurrencyAndReliability:
    """Tests 17-22: Thread safety, error recovery, bounds guards, and regression integrity."""

    def test_concurrent_engine_initialization(self) -> None:
        """Test 17: Concurrent calls to _get_engine instantiate exactly one engine instance."""
        adapter = DevanagariRapidOcrAdapter()
        results: list[Any] = []

        def init_engine() -> Any:
            return adapter._get_engine()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(init_engine) for _ in range(8)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        assert len(results) == 8
        first = results[0]
        for res in results[1:]:
            assert res is first

    def test_concurrent_inference_execution(self) -> None:
        """Test 18: Concurrent recognize_rendered_page calls are serialized safely."""
        adapter = DevanagariRapidOcrAdapter()
        img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        geom = PageGeometry(
            page_number=1,
            width=200.0,
            height=200.0,
            dpi=150.0,
            rotation_applied=0,
            original_rotation=0,
        )
        rendered_page = RenderedPage(
            page_number=1,
            image=img,
            geometry=geom,
            pixel_width=200,
            pixel_height=200,
        )

        mock_engine = MagicMock(
            return_value=([([[10, 10], [50, 10], [50, 30], [10, 30]], "परीक्षण", 0.9)], 0.01)
        )

        def run_inference() -> str:
            page = adapter.recognize_rendered_page(mock_engine, rendered_page)
            return page.raw_text

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(run_inference) for _ in range(6)]
            results = [f.result() for f in futures]

        assert len(results) == 6
        assert all(r == "परीक्षण" for r in results)

    def test_initialization_failure_cleanup(self) -> None:
        """Test 19: Initialization failure resets engine and verified artifact to None."""
        adapter = DevanagariRapidOcrAdapter()
        adapter.artifact_manager = MagicMock()
        adapter.artifact_manager.verify_artifact.side_effect = RuntimeError(
            "Simulated verification error"
        )

        with pytest.raises(RuntimeError):
            adapter._get_engine()

        assert adapter._engine is None
        assert adapter._verified_artifact is None

    def test_oversized_image_rejection(self) -> None:
        """Test 20: Oversized page dimensions are rejected with ValueError."""
        adapter = DevanagariRapidOcrAdapter()
        oversized_page = RenderedPage(
            page_number=1,
            image=Image.new("RGB", (10, 10)),
            geometry=PageGeometry(
                page_number=1,
                width=float(MAX_PIXEL_DIMENSION + 100),
                height=100.0,
                dpi=150.0,
                rotation_applied=0,
                original_rotation=0,
            ),
            pixel_width=MAX_PIXEL_DIMENSION + 100,
            pixel_height=100,
        )
        with pytest.raises(ValueError) as exc_info:
            adapter.recognize_rendered_page(MagicMock(), oversized_page)
        assert "exceeds maximum allowed" in str(exc_info.value).lower()

    def test_pii_safe_error_logging(self, tmp_path: Path) -> None:
        """Test 21: Model artifact manager scrubs absolute paths in metadata representation."""
        manager = OcrModelArtifactManager(models_dir=settings.ocr_model_dir)
        verified = manager.verify_artifact(PP_OCRV5_DEVANAGARI)
        safe_meta = verified.to_safe_metadata()

        assert "local_path" not in safe_meta
        assert str(verified.model_path) not in str(safe_meta)
        assert safe_meta["model_filename"] == "devanagari_PP-OCRv5_mobile_rec_infer.onnx"
        assert safe_meta["model_sha256"] == PP_OCRV5_DEVANAGARI.model_sha256

    def test_existing_ocr_regression_fixtures(self, tmp_path: Path) -> None:
        """Test 22: Devanagari adapter processes existing scanned document end-to-end without crashing."""
        pdf_path = tmp_path / "scanned_doc.pdf"
        create_scanned_printed_text_pdf(pdf_path)

        adapter = DevanagariRapidOcrAdapter()
        inp = AnalyzerInput(
            file_path=pdf_path,
            declared_media_type="application/pdf",
            case_id="case-e2e-01",
            document_id="doc-e2e-01",
            processing_run_id="run-e2e-01",
            document_sha256="d" * 64,
        )
        output = adapter.analyze(inp)

        assert output.status == PipelineStatus.SUCCEEDED
        assert output.analyzer_id == "ppocrv5-devanagari-engine"
        assert len(output.observations) >= 2
        page_obs = next(o for o in output.observations if o.observation_type == "ocr_page")
        assert page_obs.evidence_payload["token_count"] > 0
