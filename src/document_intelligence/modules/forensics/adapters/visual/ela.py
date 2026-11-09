"""Error Level Analysis (ELA) core computer vision algorithms.

Calculates compression rate discrepancies across document images by analyzing
the pixel-level delta between the original raster and an in-memory re-compressed
JPEG equivalent.

Thread-safe, CPU-first, in-memory execution using Pillow and OpenCV.
"""

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance

from document_intelligence.domain.enums import CoordinateSystem
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry


@dataclass(frozen=True)
class ElaRegion:
    """Localized candidate visual region exhibiting compression inconsistency."""

    bounding_box: BoundingBox
    pixel_x: int
    pixel_y: int
    pixel_w: int
    pixel_h: int
    mean_energy: float
    max_energy: float


@dataclass
class ElaPageResult:
    """Result of Error Level Analysis for a single page."""

    page_number: int
    mean_difference: float
    std_difference: float
    max_difference: float
    high_energy_ratio: float
    regions: list[ElaRegion] = field(default_factory=list)
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def compute_ela_image(
    image: Image.Image,
    quality: int = 90,
    enhancement_scale: float = 15.0,
) -> tuple[Image.Image, np.ndarray]:
    """Compute ELA difference image and energy array in-memory.

    Args:
        image: Source RGB PIL Image.
        quality: JPEG compression quality level (1-100).
        enhancement_scale: Brightness multiplier for visualization.

    Returns:
        Tuple of (enhanced_pil_image, grayscale_diff_numpy_array).
    """
    if image.mode != "RGB":
        rgb_img = image.convert("RGB")
    else:
        rgb_img = image

    # Re-compress strictly in-memory
    buffer = io.BytesIO()
    rgb_img.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)

    # Compute difference
    diff = ImageChops.difference(rgb_img, resaved)

    # Convert difference to numpy array for CV / statistical analysis
    diff_np = np.asarray(diff, dtype=np.float32)
    # Grayscale energy: maximum difference across RGB channels per pixel
    gray_energy = np.max(diff_np, axis=2)

    # Enhance difference for visual artifact preview
    enhancer = ImageEnhance.Brightness(diff)
    enhanced = enhancer.enhance(enhancement_scale)

    return enhanced, gray_energy


def localize_ela_anomalies(
    gray_energy: np.ndarray,
    page_geometry: PageGeometry,
    pixel_width: int,
    pixel_height: int,
    sigma_threshold: float = 3.0,
    min_area_pixels: int = 150,
    max_regions: int = 10,
) -> tuple[float, float, float, float, list[ElaRegion]]:
    """Analyze pixel difference energy and localize candidate visual regions with compression inconsistencies.

    Returns:
        (mean, std, max, high_energy_ratio, list[ElaRegion])
    """
    mean_val = float(np.mean(gray_energy))
    std_val = float(np.std(gray_energy))
    max_val = float(np.max(gray_energy))

    # Calculate high-energy pixel ratio
    high_threshold = max(8.0, mean_val + (sigma_threshold * std_val))
    high_pixels = np.count_nonzero(gray_energy > high_threshold)
    high_energy_ratio = float(high_pixels / gray_energy.size)

    # Binary mask for anomaly clustering
    mask = (gray_energy > high_threshold).astype(np.uint8) * 255

    # Morphological dilation and closing to merge closely adjacent edge pixels
    kernel_size = max(3, int(min(pixel_width, pixel_height) / 100))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    dilated = cv2.dilate(mask, kernel, iterations=2)
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel)

    # Find external contours
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions: list[ElaRegion] = []
    # Sort contours by area descending
    sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for cnt in sorted_contours[:max_regions]:
        area = cv2.contourArea(cnt)
        if area < min_area_pixels:
            continue

        px_x, px_y, px_w, px_h = cv2.boundingRect(cnt)

        # Region energy
        roi = gray_energy[px_y : px_y + px_h, px_x : px_x + px_w]
        reg_mean = float(np.mean(roi))
        reg_max = float(np.max(roi))

        # Calculate normalized coordinates without silent clamping
        norm_x = px_x / pixel_width
        norm_y = px_y / pixel_height
        norm_w = px_w / pixel_width
        norm_h = px_h / pixel_height

        tolerance = 1e-5
        if (
            norm_x < -tolerance
            or norm_y < -tolerance
            or (norm_x + norm_w) > 1.0 + tolerance
            or (norm_y + norm_h) > 1.0 + tolerance
        ):
            raise ValueError(
                f"ELA candidate region extends out of canonical page bounds: x={norm_x}, y={norm_y}, w={norm_w}, h={norm_h}"
            )

        bbox = BoundingBox(
            x=round(max(0.0, min(1.0, norm_x)), 6),
            y=round(max(0.0, min(1.0, norm_y)), 6),
            width=round(max(0.0, min(1.0 - norm_x, norm_w)), 6),
            height=round(max(0.0, min(1.0 - norm_y, norm_h)), 6),
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )

        regions.append(
            ElaRegion(
                bounding_box=bbox,
                pixel_x=px_x,
                pixel_y=px_y,
                pixel_w=px_w,
                pixel_h=px_h,
                mean_energy=reg_mean,
                max_energy=reg_max,
            )
        )

    return mean_val, std_val, max_val, high_energy_ratio, regions


def generate_ela_heatmap_bytes(
    enhanced_image: Image.Image,
    regions: list[ElaRegion],
) -> bytes:
    """Generate encoded PNG bytes for enhanced ELA heatmap with candidate bounding boxes."""
    vis_bgr = cv2.cvtColor(np.array(enhanced_image), cv2.COLOR_RGB2BGR)

    for reg in regions:
        # Draw bounding rectangle around candidate region
        cv2.rectangle(
            vis_bgr,
            (reg.pixel_x, reg.pixel_y),
            (reg.pixel_x + reg.pixel_w, reg.pixel_y + reg.pixel_h),
            (0, 0, 255),  # BGR Red
            2,
        )

    success, encoded = cv2.imencode(".png", vis_bgr)
    if not success:
        raise ValueError("Failed to encode ELA heatmap to PNG format.")
    return bytes(encoded)


def save_ela_heatmap(
    enhanced_image: Image.Image,
    regions: list[ElaRegion],
    output_path: Path,
) -> Path:
    """Save the enhanced ELA heatmap with bounding boxes to disk."""
    data = generate_ela_heatmap_bytes(enhanced_image, regions)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path
