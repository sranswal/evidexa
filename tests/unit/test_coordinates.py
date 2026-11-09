"""Unit tests for the canonical page-coordinate system and PageGeometry contract."""

import pytest

from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry


class TestPageGeometry:
    """Test PageGeometry properties and rotation."""

    def test_portrait_and_landscape_classification(self) -> None:
        portrait = PageGeometry(width=612.0, height=792.0, rotation=0)
        assert portrait.is_portrait is True
        assert portrait.is_landscape is False
        assert round(portrait.aspect_ratio, 4) == round(612.0 / 792.0, 4)

        landscape = PageGeometry(width=792.0, height=612.0, rotation=0)
        assert landscape.is_landscape is True
        assert landscape.is_portrait is False

    def test_invalid_rotation_rejected(self) -> None:
        with pytest.raises(ValueError, match="Page rotation must be one of"):
            PageGeometry(width=612.0, height=792.0, rotation=45)

    def test_rotated_dimensions(self) -> None:
        page = PageGeometry(width=612.0, height=792.0, rotation=90)
        w, h = page.rotated_dimensions()
        assert w == 792.0
        assert h == 612.0

        page_0 = PageGeometry(width=612.0, height=792.0, rotation=0)
        w0, h0 = page_0.rotated_dimensions()
        assert w0 == 612.0
        assert h0 == 792.0


class TestBoundingBoxCanonicalContract:
    """Test strict bounds checking, no silent clamping, zero-area, and corners."""

    def test_four_page_corners(self) -> None:
        # Top-left corner
        tl = BoundingBox(x=0.0, y=0.0, width=0.1, height=0.1)
        assert tl.x == 0.0 and tl.y == 0.0

        # Top-right corner
        tr = BoundingBox(x=0.9, y=0.0, width=0.1, height=0.1)
        assert tr.x2 == 1.0 and tr.y == 0.0

        # Bottom-left corner
        bl = BoundingBox(x=0.0, y=0.9, width=0.1, height=0.1)
        assert bl.x == 0.0 and bl.y2 == 1.0

        # Bottom-right corner
        br = BoundingBox(x=0.9, y=0.9, width=0.1, height=0.1)
        assert br.x2 == 1.0 and br.y2 == 1.0

    def test_zero_area_boxes(self) -> None:
        # Point (0 width, 0 height)
        point = BoundingBox(x=0.5, y=0.5, width=0.0, height=0.0)
        assert point.is_zero_area() is True
        assert point.area == 0.0

        # Vertical line
        vline = BoundingBox(x=0.2, y=0.1, width=0.0, height=0.5)
        assert vline.is_zero_area() is True

        # Horizontal line
        hline = BoundingBox(x=0.2, y=0.1, width=0.6, height=0.0)
        assert hline.is_zero_area() is True

        # Non-zero area
        rect = BoundingBox(x=0.1, y=0.1, width=0.5, height=0.5)
        assert rect.is_zero_area() is False
        assert rect.area == 0.25

    def test_strict_out_of_bounds_rejection_no_silent_clamping(self) -> None:
        # Negative x
        with pytest.raises(ValueError, match="x coordinate must be non-negative"):
            BoundingBox(x=-0.05, y=0.1, width=0.2, height=0.2)

        # Negative y
        with pytest.raises(ValueError, match="y coordinate must be non-negative"):
            BoundingBox(x=0.1, y=-0.01, width=0.2, height=0.2)

        # Negative width
        with pytest.raises(ValueError, match="width must be non-negative"):
            BoundingBox(x=0.1, y=0.1, width=-0.1, height=0.2)

        # Negative height
        with pytest.raises(ValueError, match="height must be non-negative"):
            BoundingBox(x=0.1, y=0.1, width=0.2, height=-0.2)

        # Extends horizontally past page boundary (> 1.0)
        with pytest.raises(ValueError, match="extends out of page bounds horizontally"):
            BoundingBox(x=0.8, y=0.1, width=0.3, height=0.2)

        # Extends vertically past page boundary (> 1.0)
        with pytest.raises(ValueError, match="extends out of page bounds vertically"):
            BoundingBox(x=0.1, y=0.7, width=0.2, height=0.4)

    def test_pdf_points_to_normalized_conversion(self) -> None:
        page_w = 612.0
        page_h = 792.0

        # PDF native: (0, 0) at bottom-left
        # Let's say a box is at bottom-left in PDF: x0=0, y0=0, x1=100, y1=50
        # In canonical top-left standard:
        # norm_x = 0 / 612 = 0.0
        # norm_y = (792 - 50) / 792 = 742 / 792
        # norm_w = 100 / 612
        # norm_h = 50 / 792
        bbox = BoundingBox.from_pdf_points(
            x0=0.0, y0=0.0, x1=100.0, y1=50.0, page_width=page_w, page_height=page_h
        )
        assert bbox.x == 0.0
        assert round(bbox.y, 4) == round((792.0 - 50.0) / 792.0, 4)
        assert round(bbox.width, 4) == round(100.0 / 612.0, 4)
        assert round(bbox.height, 4) == round(50.0 / 792.0, 4)

    def test_round_trip_pdf_points_conversion(self) -> None:
        page_w = 595.0  # A4 width
        page_h = 842.0  # A4 height

        orig_x0, orig_y0, orig_x1, orig_y1 = 50.0, 100.0, 250.0, 300.0

        bbox = BoundingBox.from_pdf_points(
            x0=orig_x0, y0=orig_y0, x1=orig_x1, y1=orig_y1, page_width=page_w, page_height=page_h
        )
        rt_x0, rt_y0, rt_x1, rt_y1 = bbox.to_pdf_points(page_width=page_w, page_height=page_h)

        assert pytest.approx(orig_x0, abs=1e-2) == rt_x0
        assert pytest.approx(orig_y0, abs=1e-2) == rt_y0
        assert pytest.approx(orig_x1, abs=1e-2) == rt_x1
        assert pytest.approx(orig_y1, abs=1e-2) == rt_y1

    def test_page_rotations(self) -> None:
        page = PageGeometry(width=1000.0, height=1000.0, rotation=0)
        # Top-left quadrant: x=0.1, y=0.1, w=0.2, h=0.3
        box = BoundingBox(x=0.1, y=0.1, width=0.2, height=0.3)

        # 90 degrees clockwise rotation:
        # new_x = 1 - (old_y + old_h) = 1 - 0.4 = 0.6
        # new_y = old_x = 0.1
        # new_w = old_h = 0.3
        # new_h = old_w = 0.2
        r90 = box.apply_rotation(page, 90)
        assert pytest.approx(r90.x, abs=1e-5) == 0.6
        assert pytest.approx(r90.y, abs=1e-5) == 0.1
        assert pytest.approx(r90.width, abs=1e-5) == 0.3
        assert pytest.approx(r90.height, abs=1e-5) == 0.2

        # 180 degrees clockwise rotation:
        # new_x = 1 - (old_x + old_w) = 1 - 0.3 = 0.7
        # new_y = 1 - (old_y + old_h) = 1 - 0.4 = 0.6
        # new_w = old_w = 0.2
        # new_h = old_h = 0.3
        r180 = box.apply_rotation(page, 180)
        assert pytest.approx(r180.x, abs=1e-5) == 0.7
        assert pytest.approx(r180.y, abs=1e-5) == 0.6
        assert pytest.approx(r180.width, abs=1e-5) == 0.2
        assert pytest.approx(r180.height, abs=1e-5) == 0.3

        # 270 degrees clockwise rotation:
        # new_x = old_y = 0.1
        # new_y = 1 - (old_x + old_w) = 1 - 0.3 = 0.7
        # new_w = old_h = 0.3
        # new_h = old_w = 0.2
        r270 = box.apply_rotation(page, 270)
        assert pytest.approx(r270.x, abs=1e-5) == 0.1
        assert pytest.approx(r270.y, abs=1e-5) == 0.7
        assert pytest.approx(r270.width, abs=1e-5) == 0.3
        assert pytest.approx(r270.height, abs=1e-5) == 0.2
