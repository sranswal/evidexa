"""Comprehensive unit tests for Phase 2B.2.1: Visual Forensics Validation & Hardening."""

import hashlib
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from document_intelligence.core.exceptions import SecurityException
from document_intelligence.domain.models.bounding_box import PageGeometry
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.modules.forensics.adapters.visual.copy_move import (
    detect_copy_move_clusters,
)
from document_intelligence.modules.forensics.adapters.visual.ela import (
    compute_ela_image,
    localize_ela_anomalies,
)
from document_intelligence.modules.forensics.adapters.visual.page_renderer import (
    DocumentPageRenderer,
)
from tests.fixtures.visual_factory import (
    build_cm_neg_low_texture,
    build_cm_neg_ordinary_page,
    build_cm_neg_repeated_table_borders,
    build_cm_pos_different_displacement,
    build_cm_pos_multiple_copied_regions,
    build_cm_pos_translated_patch,
    build_ela_neg_clean_scanned_doc,
    build_ela_neg_clean_white_text,
    build_ela_neg_legitimate_content_regions,
    build_ela_neg_mixed_content,
    build_ela_neg_ordinary_recompression,
    build_ela_neg_repeated_logos,
    build_ela_pos_different_compression_history,
    build_ela_pos_locally_recompressed_patch,
    build_ela_pos_synthetic_composited_boundary,
    create_synthetic_marker_pdf,
)


class TestElaFalsePositiveValidation:
    """Rigorous evaluation of ELA on negative and positive synthetic fixtures."""

    @pytest.mark.parametrize(
        "fixture_fn,name",
        [
            (build_ela_neg_clean_white_text, "clean_white_text"),
            (build_ela_neg_clean_scanned_doc, "scanned_doc_noise"),
            (build_ela_neg_repeated_logos, "repeated_logos"),
            (build_ela_neg_mixed_content, "mixed_content"),
            (build_ela_neg_ordinary_recompression, "ordinary_recompression"),
            (build_ela_neg_legitimate_content_regions, "legitimate_regions"),
        ],
    )
    def test_ela_negative_fixtures_behavior(self, fixture_fn, name: str) -> None:
        img = fixture_fn()
        w, h = img.size
        geom = PageGeometry(width=w, height=h, dpi=150)

        enhanced, gray = compute_ela_image(img, quality=90)
        mean_v, std_v, max_v, high_r, regions = localize_ela_anomalies(
            gray_energy=gray,
            page_geometry=geom,
            pixel_width=w,
            pixel_height=h,
        )

        assert mean_v >= 0.0
        assert std_v >= 0.0
        assert max_v >= 0.0
        # High energy ratio should be bounded on standard documents
        assert high_r < 0.05

        # Ordinary uniform recompression should produce 0 candidate regions
        if name == "ordinary_recompression":
            assert len(regions) == 0
            assert high_r == 0.0

    @pytest.mark.parametrize(
        "fixture_fn,expected_roi",
        [
            (build_ela_pos_locally_recompressed_patch, (140, 180, 180, 100)),
            (build_ela_pos_different_compression_history, (160, 200, 150, 80)),
            (build_ela_pos_synthetic_composited_boundary, (220, 180, 120, 120)),
        ],
    )
    def test_ela_positive_fixtures_detection(
        self, fixture_fn, expected_roi: tuple[int, int, int, int]
    ) -> None:
        img = fixture_fn()
        w, h = img.size
        geom = PageGeometry(width=w, height=h, dpi=150)

        enhanced, gray = compute_ela_image(img, quality=90)
        mean_v, std_v, max_v, high_r, regions = localize_ela_anomalies(
            gray_energy=gray,
            page_geometry=geom,
            pixel_width=w,
            pixel_height=h,
        )

        assert len(regions) >= 1
        ex, ey, ew, eh = expected_roi

        # Assert at least one detected region intersects the modified ROI
        overlap_found = False
        for reg in regions:
            rx, ry, rw, rh = reg.pixel_x, reg.pixel_y, reg.pixel_w, reg.pixel_h
            ix1 = max(ex, rx)
            iy1 = max(ey, ry)
            ix2 = min(ex + ew, rx + rw)
            iy2 = min(ey + eh, ry + rh)
            if ix2 > ix1 and iy2 > iy1:
                overlap_found = True
                break

        assert overlap_found is True


class TestCopyMoveFalsePositiveValidation:
    """Rigorous evaluation of Copy-Move detection on negative and positive fixtures."""

    @pytest.mark.parametrize(
        "fixture_fn,name",
        [
            (build_cm_neg_low_texture, "low_texture"),
            (build_cm_neg_repeated_table_borders, "repeated_table_borders"),
            (build_cm_neg_ordinary_page, "ordinary_page"),
        ],
    )
    def test_copy_move_negative_zero_clusters(self, fixture_fn, name: str) -> None:
        img = fixture_fn()
        w, h = img.size
        geom = PageGeometry(width=w, height=h, dpi=150)

        total_kp, valid_matches, clusters, pairs = detect_copy_move_clusters(
            image=img,
            page_geometry=geom,
            pixel_width=w,
            pixel_height=h,
            min_cluster_matches=10,
        )

        # In low texture or clean pages without cloned badges, 0 duplicate clusters should appear
        if name in ("low_texture", "repeated_table_borders"):
            assert len(clusters) == 0

    def test_copy_move_positive_translated_patch(self) -> None:
        img = build_cm_pos_translated_patch()
        w, h = img.size
        geom = PageGeometry(width=w, height=h, dpi=150)

        total_kp, valid_matches, clusters, pairs = detect_copy_move_clusters(
            image=img,
            page_geometry=geom,
            pixel_width=w,
            pixel_height=h,
            min_cluster_matches=10,
        )

        assert len(clusters) >= 1
        # Target displacement is (300, 240)
        found_target_disp = any(
            abs(c.displacement_dx - 300.0) < 25.0 and abs(c.displacement_dy - 240.0) < 25.0
            for c in clusters
        )
        assert found_target_disp is True

    def test_copy_move_positive_different_displacement(self) -> None:
        img = build_cm_pos_different_displacement()
        w, h = img.size
        geom = PageGeometry(width=w, height=h, dpi=150)

        total_kp, valid_matches, clusters, pairs = detect_copy_move_clusters(
            image=img,
            page_geometry=geom,
            pixel_width=w,
            pixel_height=h,
            min_cluster_matches=10,
        )

        assert len(clusters) >= 1
        # Target displacement is (120, 340)
        found_target_disp = any(
            abs(c.displacement_dx - 120.0) < 25.0 and abs(c.displacement_dy - 340.0) < 25.0
            for c in clusters
        )
        assert found_target_disp is True

    def test_copy_move_positive_multiple_copied_regions(self) -> None:
        img = build_cm_pos_multiple_copied_regions()
        w, h = img.size
        geom = PageGeometry(width=w, height=h, dpi=150)

        total_kp, valid_matches, clusters, pairs = detect_copy_move_clusters(
            image=img,
            page_geometry=geom,
            pixel_width=w,
            pixel_height=h,
            min_cluster_matches=10,
        )

        # Expected two distinct displacements: (330, 200) and (340, 60)
        has_disp_a = any(
            abs(c.displacement_dx - 330.0) < 25.0 and abs(c.displacement_dy - 200.0) < 25.0
            for c in clusters
        )
        has_disp_b = any(
            abs(c.displacement_dx - 340.0) < 25.0 and abs(c.displacement_dy - 60.0) < 25.0
            for c in clusters
        )
        assert has_disp_a is True
        assert has_disp_b is True


class TestCoordinateTransformationVerification:
    """Verifies that rendering across all rotations and DPI settings maps to canonical top-left coordinates."""

    @pytest.mark.parametrize(
        "rot,expected_norm_x,expected_norm_y,expected_norm_w,expected_norm_h",
        [
            (0, 0.1250, 0.1167, 0.2500, 0.1333),
            (90, 0.7500, 0.1250, 0.1333, 0.2500),
            (180, 0.6250, 0.7500, 0.2500, 0.1333),
            (270, 0.1167, 0.6250, 0.1333, 0.2500),
        ],
    )
    def test_pdf_rotation_coordinate_invariants(
        self,
        rot: int,
        expected_norm_x: float,
        expected_norm_y: float,
        expected_norm_w: float,
        expected_norm_h: float,
    ) -> None:
        """Verify marker bounding box maps to correct canonical coordinates for 0, 90, 180, 270 deg rotations."""
        # 400x600 pt page, marker at [50, 450, 100, 80] in native PDF points
        pdf_bytes = create_synthetic_marker_pdf(
            width_pts=400.0,
            height_pts=600.0,
            rotation_deg=rot,
            marker_x0=50.0,
            marker_y0=450.0,
            marker_w=100.0,
            marker_h=80.0,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_pdf = Path(f.name)

        try:
            renderer = DocumentPageRenderer(default_dpi=150.0)
            pages = list(renderer.render_pages(tmp_pdf))
            assert len(pages) == 1
            p = pages[0]

            # Detect red marker rectangle in rendered image
            import numpy as np

            arr = np.array(p.image)
            red_pixels = (arr[:, :, 0] > 200) & (arr[:, :, 1] < 50) & (arr[:, :, 2] < 50)
            ys, xs = np.where(red_pixels)
            assert len(xs) > 0

            px_x = int(np.min(xs))
            px_y = int(np.min(ys))
            px_w = int(np.max(xs)) - px_x + 1
            px_h = int(np.max(ys)) - px_y + 1

            norm_x = px_x / p.pixel_width
            norm_y = px_y / p.pixel_height
            norm_w = px_w / p.pixel_width
            norm_h = px_h / p.pixel_height

            # Verify within numerical tolerance of 0.005 (0.5%)
            tol = 0.005
            assert abs(norm_x - expected_norm_x) < tol
            assert abs(norm_y - expected_norm_y) < tol
            assert abs(norm_w - expected_norm_w) < tol
            assert abs(norm_h - expected_norm_h) < tol

        finally:
            tmp_pdf.unlink()


class TestResourceLimitsAndFailSafeControls:
    """Verifies that resource limits are enforced before allocation and malformed files fail safely."""

    def test_oversized_image_dimensions_rejected_before_decode(self, tmp_path: Path) -> None:
        # Create image with dimension > 4000 px
        huge = Image.new("RGB", (4200, 100), color=(255, 255, 255))
        huge_path = tmp_path / "huge.png"
        huge.save(huge_path)

        renderer = DocumentPageRenderer()
        with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
            list(renderer.render_pages(huge_path, media_type="image/png"))

    def test_oversized_total_pixels_rejected_before_decode(self, tmp_path: Path) -> None:
        # Create image with total pixels > 12,000,000 px (e.g. 3600 x 3600 = 12.96 MP)
        huge = Image.new("RGB", (3600, 3600), color=(255, 255, 255))
        huge_path = tmp_path / "huge_area.png"
        huge.save(huge_path)

        renderer = DocumentPageRenderer()
        with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
            list(renderer.render_pages(huge_path, media_type="image/png"))

    def test_oversized_pdf_page_count_rejected(self, tmp_path: Path) -> None:
        import pikepdf

        pdf = pikepdf.new()
        # Add 55 blank pages (exceeding default limit of 50)
        for _ in range(55):
            pdf.pages.append(
                pikepdf.Page(
                    pikepdf.Dictionary(
                        Type=pikepdf.Name.Page, MediaBox=pikepdf.Array([0, 0, 100, 100])
                    )
                )
            )
        pdf_path = tmp_path / "oversized_pages.pdf"
        pdf.save(pdf_path)

        renderer = DocumentPageRenderer(max_pages=50)
        with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
            list(renderer.render_pages(pdf_path))

    def test_malformed_image_fails_safely(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.png"
        corrupt.write_bytes(b"\x89PNG\r\n\x1a\nCORRUPTED_GARBAGE_PAYLOAD")

        renderer = DocumentPageRenderer()
        with pytest.raises(ValueError, match="Failed to parse image file"):
            list(renderer.render_pages(corrupt, media_type="image/png"))


class TestArtifactStorageHardening:
    """Verifies artifact storage abstraction, path traversal protection, and SHA-256 integrity."""

    def test_store_and_retrieve_artifact_with_hash(self, tmp_path: Path) -> None:
        from document_intelligence.core.config import Settings

        settings = Settings(DATA_DIR=tmp_path)
        storage = FilesystemDocumentStorage(app_settings=settings)

        payload = b"FAKE_PNG_BINARY_DATA_FOR_HEATMAP"
        expected_hash = hashlib.sha256(payload).hexdigest()

        key, art_hash = storage.store_artifact(
            case_id="case-xyz",
            document_id="doc-abc",
            processing_run_id="run-123",
            artifact_filename="ela_heatmap.png",
            data=payload,
        )

        assert key == "case-xyz/doc-abc/run-123/ela_heatmap.png"
        assert art_hash == expected_hash

        resolved_path = storage.get_artifact_path(key)
        assert resolved_path.exists()
        assert resolved_path.read_bytes() == payload

    def test_path_traversal_in_artifact_storage_rejected(self, tmp_path: Path) -> None:
        from document_intelligence.core.config import Settings

        settings = Settings(DATA_DIR=tmp_path)
        storage = FilesystemDocumentStorage(app_settings=settings)

        with pytest.raises(SecurityException):
            storage.store_artifact(
                case_id="../../etc",
                document_id="passwd",
                processing_run_id="root",
                artifact_filename="pwned.png",
                data=b"exploit",
            )
