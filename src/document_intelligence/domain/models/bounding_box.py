"""Canonical page-coordinate system and bounding box geometry representation."""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from document_intelligence.domain.enums import CoordinateSystem

ALLOWED_ROTATIONS = {0, 90, 180, 270}


class PageGeometry(BaseModel):
    """Physical and rotational geometry of a document page.

    Canonical origin is top-left (0,0) of the unrotated raster/canvas.
    """

    width: float = Field(gt=0, description="Page width in points or pixels")
    height: float = Field(gt=0, description="Page height in points or pixels")
    rotation: int = Field(default=0, description="Page rotation angle in degrees (0, 90, 180, 270)")
    dpi: float | None = Field(
        default=72.0, gt=0, description="Raster resolution DPI (default 72 for PDF points)"
    )

    @field_validator("rotation")
    @classmethod
    def validate_rotation(cls, v: int) -> int:
        if v not in ALLOWED_ROTATIONS:
            raise ValueError(
                f"Page rotation must be one of {sorted(ALLOWED_ROTATIONS)} degrees, got {v}."
            )
        return v

    @property
    def is_portrait(self) -> bool:
        """True if page height is greater than or equal to page width."""
        return self.height >= self.width

    @property
    def is_landscape(self) -> bool:
        """True if page width is strictly greater than page height."""
        return self.width > self.height

    @property
    def aspect_ratio(self) -> float:
        """Ratio of width to height."""
        return self.width / self.height

    def rotated_dimensions(self) -> tuple[float, float]:
        """Dimensions after applying rotation."""
        if self.rotation in {90, 270}:
            return self.height, self.width
        return self.width, self.height


class BoundingBox(BaseModel):
    """Canonical spatial bounding box representation.

    Canonical Coordinate Standards:
    - Origin: Top-Left (0.0, 0.0) of the page display.
    - Horizontal axis (X): increases from left to right.
    - Vertical axis (Y): increases from top to bottom.
    - Normalized Coordinates (NORMALIZED_0_1): values are ratios in [0.0, 1.0] relative to page dimensions.
    - Out-of-bounds coordinates are strictly rejected with validation errors; NEVER clamped silently.
    """

    x: float = Field(description="Top-left horizontal coordinate")
    y: float = Field(description="Top-left vertical coordinate")
    width: float = Field(description="Horizontal width dimension")
    height: float = Field(description="Vertical height dimension")
    coordinate_system: CoordinateSystem = Field(
        default=CoordinateSystem.NORMALIZED_0_1,
        description="Coordinate system representation",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_geometry(cls, data: Any) -> Any:
        if isinstance(data, dict):
            width = data.get("width")
            height = data.get("height")
            x = data.get("x")
            y = data.get("y")
            coord_sys = data.get("coordinate_system", CoordinateSystem.NORMALIZED_0_1)

            # Check 1: Non-negativity
            if width is not None and width < 0:
                raise ValueError(f"BoundingBox width must be non-negative, got {width}.")
            if height is not None and height < 0:
                raise ValueError(f"BoundingBox height must be non-negative, got {height}.")
            if x is not None and x < 0:
                raise ValueError(f"BoundingBox x coordinate must be non-negative, got {x}.")
            if y is not None and y < 0:
                raise ValueError(f"BoundingBox y coordinate must be non-negative, got {y}.")

            # Check 2: Bounds validation for normalized coordinates
            # Tolerance 1e-5 to accommodate floating-point rounding
            if coord_sys in {CoordinateSystem.NORMALIZED_0_1, "NORMALIZED_0_1"}:
                tolerance = 1e-5
                if x is not None and width is not None:
                    if x + width > 1.0 + tolerance:
                        raise ValueError(
                            f"BoundingBox extends out of page bounds horizontally: x={x} + width={width} = {x + width:.5f} > 1.0"
                        )
                if y is not None and height is not None:
                    if y + height > 1.0 + tolerance:
                        raise ValueError(
                            f"BoundingBox extends out of page bounds vertically: y={y} + height={height} = {y + height:.5f} > 1.0"
                        )

        return data

    @property
    def area(self) -> float:
        """Spatial area of bounding box."""
        return self.width * self.height

    def is_zero_area(self) -> bool:
        """True if bounding box has zero area (point or line)."""
        return self.width == 0.0 or self.height == 0.0

    @property
    def x2(self) -> float:
        """Right coordinate boundary."""
        return self.x + self.width

    @property
    def y2(self) -> float:
        """Bottom coordinate boundary."""
        return self.y + self.height

    def to_absolute(self, page: PageGeometry) -> "BoundingBox":
        """Convert normalized coordinates to absolute page dimensions."""
        if self.coordinate_system != CoordinateSystem.NORMALIZED_0_1:
            return self

        return BoundingBox(
            x=self.x * page.width,
            y=self.y * page.height,
            width=self.width * page.width,
            height=self.height * page.height,
            coordinate_system=CoordinateSystem.PDF_POINTS
            if page.dpi == 72.0
            else CoordinateSystem.PIXEL_EXACT,
        )

    def to_normalized(self, page: PageGeometry) -> "BoundingBox":
        """Convert absolute coordinates to normalized [0.0, 1.0] coordinates."""
        if self.coordinate_system == CoordinateSystem.NORMALIZED_0_1:
            return self

        return BoundingBox(
            x=min(max(self.x / page.width, 0.0), 1.0),
            y=min(max(self.y / page.height, 0.0), 1.0),
            width=min(self.width / page.width, 1.0),
            height=min(self.height / page.height, 1.0),
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )

    @classmethod
    def from_pdf_points(
        cls,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        page_width: float,
        page_height: float,
    ) -> "BoundingBox":
        """Convert native PDF bottom-left points to canonical top-left normalized coordinates.

        In PDF standard coordinates:
        - Origin (0,0) is at Bottom-Left.
        - Y increases upward.

        In canonical platform coordinates:
        - Origin (0,0) is at Top-Left.
        - Y increases downward.
        """
        if page_width <= 0 or page_height <= 0:
            raise ValueError(
                f"Page dimensions must be strictly positive: {page_width}x{page_height}"
            )

        min_x = min(x0, x1)
        max_x = max(x0, x1)
        min_y = min(y0, y1)
        max_y = max(y0, y1)

        norm_x = min_x / page_width
        norm_y = (page_height - max_y) / page_height
        norm_w = (max_x - min_x) / page_width
        norm_h = (max_y - min_y) / page_height

        return cls(
            x=round(norm_x, 6),
            y=round(norm_y, 6),
            width=round(norm_w, 6),
            height=round(norm_h, 6),
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )

    def to_pdf_points(
        self, page_width: float, page_height: float
    ) -> tuple[float, float, float, float]:
        """Convert canonical top-left normalized coordinates back to PDF bottom-left points (x0, y0, x1, y1)."""
        if self.coordinate_system != CoordinateSystem.NORMALIZED_0_1:
            raise ValueError("to_pdf_points requires normalized coordinates.")

        x0 = self.x * page_width
        x1 = (self.x + self.width) * page_width
        y1 = (1.0 - self.y) * page_height
        y0 = (1.0 - (self.y + self.height)) * page_height

        return x0, y0, x1, y1

    def apply_rotation(self, page: PageGeometry, rotation_degrees: int) -> "BoundingBox":
        """Transform normalized coordinates when page is rotated clockwise by 0, 90, 180, or 270 degrees."""
        if rotation_degrees not in ALLOWED_ROTATIONS:
            raise ValueError(
                f"Rotation must be one of {sorted(ALLOWED_ROTATIONS)}, got {rotation_degrees}"
            )

        if rotation_degrees == 0:
            return self

        # Ensure we are operating in normalized coordinates
        norm_box = (
            self
            if self.coordinate_system == CoordinateSystem.NORMALIZED_0_1
            else self.to_normalized(page)
        )

        if rotation_degrees == 90:
            # 90 deg clockwise: new_x = 1 - (old_y + old_h), new_y = old_x, new_w = old_h, new_h = old_w
            new_x = 1.0 - (norm_box.y + norm_box.height)
            new_y = norm_box.x
            new_w = norm_box.height
            new_h = norm_box.width
        elif rotation_degrees == 180:
            # 180 deg: new_x = 1 - (old_x + old_w), new_y = 1 - (old_y + old_h), new_w = old_w, new_h = old_h
            new_x = 1.0 - (norm_box.x + norm_box.width)
            new_y = 1.0 - (norm_box.y + norm_box.height)
            new_w = norm_box.width
            new_h = norm_box.height
        else:  # 270 deg
            # 270 deg clockwise: new_x = old_y, new_y = 1 - (old_x + old_w), new_w = old_h, new_h = old_w
            new_x = norm_box.y
            new_y = 1.0 - (norm_box.x + norm_box.width)
            new_w = norm_box.height
            new_h = norm_box.width

        return BoundingBox(
            x=round(max(0.0, min(1.0, new_x)), 6),
            y=round(max(0.0, min(1.0, new_y)), 6),
            width=round(max(0.0, min(1.0, new_w)), 6),
            height=round(max(0.0, min(1.0, new_h)), 6),
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )

    def to_normalized_dict(self) -> dict[str, float]:
        """Export coordinates as standard dictionary."""
        return {
            "x": round(self.x, 6),
            "y": round(self.y, 6),
            "width": round(self.width, 6),
            "height": round(self.height, 6),
        }
