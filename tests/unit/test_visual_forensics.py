"""Unit tests for Visual Forensics components: PageRenderer, ELA, and Copy-Move."""

from pathlib import Path

import pytest

from document_intelligence.domain.enums import CoordinateSystem, PipelineStatus
from document_intelligence.domain.models.bounding_box import PageGeometry
from document_intelligence.modules.forensics.adapters.visual.copy_move import (
    detect_copy_move_clusters,
    save_copy_move_visualization,
)
from document_intelligence.modules.forensics.adapters.visual.copy_move_adapter import (
    CopyMoveAnalyzer,
)
from document_intelligence.modules.forensics.adapters.visual.ela import (
    compute_ela_image,
    localize_ela_anomalies,
    save_ela_heatmap,
)
from document_intelligence.modules.forensics.adapters.visual.ela_adapter import ElaAnalyzer
from document_intelligence.modules.forensics.adapters.visual.page_renderer import (
    DocumentPageRenderer,
)
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from tests.fixtures.visual_factory import (
    build_clean_image,
    build_copy_move_image,
    build_ela_spliced_image,
    save_image_as_pdf,
)


class TestDocumentPageRenderer:
    """Tests for safe rasterization and image loading."""

    def test_render_direct_image(self, tmp_path: Path) -> None:
        img = build_clean_image(300, 200)
        img_path = tmp_path / "test_doc.png"
        img.save(img_path)

        renderer = DocumentPageRenderer(default_dpi=150.0)
        pages = list(renderer.render_pages(img_path, media_type="image/png"))

        assert len(pages) == 1
        page = pages[0]
        assert page.page_number == 1
        assert page.pixel_width == 300
        assert page.pixel_height == 200
        assert page.geometry.dpi == 150.0
        assert page.image.mode == "RGB"

    def test_render_pdf_page(self, tmp_path: Path) -> None:
        img = build_clean_image(400, 300)
        pdf_path = tmp_path / "test_doc.pdf"
        save_image_as_pdf(img, pdf_path)

        renderer = DocumentPageRenderer(default_dpi=150.0)
        pages = list(renderer.render_pages(pdf_path, media_type="application/pdf"))

        assert len(pages) == 1
        page = pages[0]
        assert page.page_number == 1
        assert page.pixel_width > 0
        assert page.pixel_height > 0
        assert page.geometry.rotation in {0, 90, 180, 270}

    def test_nonexistent_file_raises_not_found(self, tmp_path: Path) -> None:
        renderer = DocumentPageRenderer()
        with pytest.raises(FileNotFoundError):
            list(renderer.render_pages(tmp_path / "missing.pdf"))


class TestErrorLevelAnalysisCore:
    """Tests for core ELA algorithms."""

    def test_clean_image_low_difference(self) -> None:
        clean = build_clean_image(300, 300)
        enhanced, gray_diff = compute_ela_image(clean, quality=90)

        assert enhanced.size == (300, 300)
        assert gray_diff.shape == (300, 300)
        mean_diff = float(gray_diff.mean())
        # Clean synthetic drawing has minimal difference
        assert mean_diff < 15.0

    def test_spliced_image_detects_high_energy_anomaly(self, tmp_path: Path) -> None:
        spliced = build_ela_spliced_image(400, 400)
        enhanced, gray_diff = compute_ela_image(spliced, quality=90)

        geom = PageGeometry(width=400, height=400, dpi=150)
        mean, std, max_v, high_ratio, regions = localize_ela_anomalies(
            gray_energy=gray_diff,
            page_geometry=geom,
            pixel_width=400,
            pixel_height=400,
            sigma_threshold=2.5,
            min_area_pixels=80,
        )

        assert max_v > 20.0
        assert high_ratio > 0.001
        assert len(regions) >= 1

        # Check bounding box canonical normalization [0.0, 1.0]
        reg = regions[0]
        assert 0.0 <= reg.bounding_box.x <= 1.0
        assert 0.0 <= reg.bounding_box.y <= 1.0
        assert 0.0 <= reg.bounding_box.width <= 1.0
        assert 0.0 <= reg.bounding_box.height <= 1.0
        assert reg.bounding_box.coordinate_system == CoordinateSystem.NORMALIZED_0_1

        # Test heatmap saving
        out_art = tmp_path / "ela_art.png"
        save_ela_heatmap(enhanced, regions, out_art)
        assert out_art.exists()
        assert out_art.stat().st_size > 0


class TestCopyMoveDetectionCore:
    """Tests for ORB keypoint and displacement clustering copy-move algorithms."""

    def test_clean_image_has_no_duplicate_clusters(self) -> None:
        clean = build_clean_image(400, 400)
        geom = PageGeometry(width=400, height=400, dpi=150)

        total_kp, matches, clusters, pairs = detect_copy_move_clusters(
            image=clean,
            page_geometry=geom,
            pixel_width=400,
            pixel_height=400,
            min_cluster_matches=10,
        )
        assert len(clusters) == 0

    def test_cloned_image_identifies_paired_clusters(self, tmp_path: Path) -> None:
        cloned = build_copy_move_image(600, 600)
        geom = PageGeometry(width=600, height=600, dpi=150)

        total_kp, matches, clusters, pairs = detect_copy_move_clusters(
            image=cloned,
            page_geometry=geom,
            pixel_width=600,
            pixel_height=600,
            min_spatial_distance_px=50.0,
            min_cluster_matches=4,
        )

        assert total_kp > 50
        assert len(clusters) >= 1

        cluster = clusters[0]
        # Verified displacement between (60, 80) and (360, 320): dx ~ 300, dy ~ 240
        assert 260.0 <= abs(cluster.displacement_dx) <= 340.0
        assert 200.0 <= abs(cluster.displacement_dy) <= 280.0
        assert cluster.matched_keypoints_count >= 4

        # Validate source and duplicate bounding boxes
        for box in (cluster.source_box, cluster.duplicate_box):
            assert 0.0 <= box.x <= 1.0
            assert 0.0 <= box.y <= 1.0
            assert 0.0 <= box.width <= 1.0
            assert 0.0 <= box.height <= 1.0
            assert box.coordinate_system == CoordinateSystem.NORMALIZED_0_1

        # Test visualization saving
        art_path = tmp_path / "copymove_art.png"
        save_copy_move_visualization(cloned, clusters, pairs, art_path)
        assert art_path.exists()
        assert art_path.stat().st_size > 0


class TestElaAnalyzerAdapter:
    """Tests for ElaAnalyzer implementing ForensicAnalyzer."""

    def test_analyzer_contract_and_clean_run(self, tmp_path: Path) -> None:
        artifacts_dir = tmp_path / "artifacts"
        analyzer = ElaAnalyzer(artifacts_dir=artifacts_dir)

        assert analyzer.analyzer_id == "ela-analyzer"
        assert analyzer.can_analyze("application/pdf") is True
        assert analyzer.can_analyze("image/png") is True
        assert analyzer.can_analyze("video/mp4") is False

        img = build_clean_image(300, 300)
        doc_path = tmp_path / "clean.png"
        img.save(doc_path)

        inp = AnalyzerInput(
            document_id="doc-101",
            case_id="case-101",
            processing_run_id="run-101",
            file_path=doc_path,
            document_sha256="fake_sha256",
            declared_media_type="image/png",
            detected_media_type="image/png",
        )

        output = analyzer.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED
        assert output.analyzer_id == "ela-analyzer"
        assert output.execution_duration_ms > 0
        assert len(output.capabilities_executed) == 1
        assert len(output.limitations) >= 1

    def test_analyzer_spliced_observation_integrity(self, tmp_path: Path) -> None:
        artifacts_dir = tmp_path / "artifacts"
        analyzer = ElaAnalyzer(artifacts_dir=artifacts_dir)

        spliced = build_ela_spliced_image(400, 400)
        doc_path = tmp_path / "spliced.png"
        spliced.save(doc_path)

        inp = AnalyzerInput(
            document_id="doc-102",
            case_id="case-102",
            processing_run_id="run-102",
            file_path=doc_path,
            document_sha256="fake_sha256_spliced",
            declared_media_type="image/png",
            detected_media_type="image/png",
        )

        output = analyzer.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED
        assert len(output.observations) >= 1

        obs = output.observations[0]
        assert obs.observation_type == "visual_ela"
        # Strict platform rule: uncalibrated local heuristics MUST NOT fabricate numeric confidence
        assert obs.confidence is None
        assert obs.categorical_confidence in {"low", "medium"}
        assert obs.confidence_source == "local:ela"
        assert obs.bounding_box is not None
        assert len(obs.benign_explanations) >= 1
        assert "artifact_path" in obs.evidence_payload


class TestCopyMoveAnalyzerAdapter:
    """Tests for CopyMoveAnalyzer implementing ForensicAnalyzer."""

    def test_analyzer_cloned_observation_integrity(self, tmp_path: Path) -> None:
        artifacts_dir = tmp_path / "artifacts"
        analyzer = CopyMoveAnalyzer(artifacts_dir=artifacts_dir)

        assert analyzer.analyzer_id == "copy-move-analyzer"
        assert analyzer.can_analyze("application/pdf") is True
        assert analyzer.can_analyze("image/jpeg") is True

        cloned = build_copy_move_image(600, 600)
        doc_path = tmp_path / "cloned.png"
        cloned.save(doc_path)

        inp = AnalyzerInput(
            document_id="doc-201",
            case_id="case-201",
            processing_run_id="run-201",
            file_path=doc_path,
            document_sha256="fake_sha256_cloned",
            declared_media_type="image/png",
            detected_media_type="image/png",
        )

        output = analyzer.analyze(inp)
        assert output.status == PipelineStatus.SUCCEEDED
        assert len(output.observations) >= 1

        obs = output.observations[0]
        assert obs.observation_type == "visual_copymove"
        assert obs.confidence is None
        assert obs.categorical_confidence in {"low", "medium"}
        assert obs.confidence_source == "local:copymove"
        # Both source and duplicate bounding boxes must be preserved
        assert obs.bounding_box is not None  # duplicate box
        assert "source_bounding_box" in obs.evidence_payload
        assert "duplicate_bounding_box" in obs.evidence_payload
        assert "displacement_dx" in obs.evidence_payload
        assert len(obs.benign_explanations) >= 1
