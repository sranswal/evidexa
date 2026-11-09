"""Document page renderer supporting PDF rasterization and direct image loading.

License compliance: Uses pypdfium2 (Apache-2.0 / BSD-3-Clause) wrapping PDFium.
Strictly avoids AGPL-licensed libraries (e.g., PyMuPDF / fitz).
"""

import logging
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from document_intelligence.domain.models.bounding_box import PageGeometry

logger = logging.getLogger(__name__)

# Resource limits to prevent resource exhaustion / DoS
MAX_PAGES_DEFAULT = 50
MAX_PIXEL_DIMENSION = 4000
MAX_TOTAL_PIXELS = 12_000_000  # 12 MP


@dataclass(frozen=True)
class RenderedPage:
    """Rasterized page image alongside canonical geometry metadata."""

    page_number: int  # 1-indexed
    image: Image.Image  # RGB PIL Image
    geometry: PageGeometry
    pixel_width: int
    pixel_height: int


class DocumentPageRenderer:
    """Safely renders document pages from PDF snapshots or direct image files with bounded resources."""

    def __init__(
        self,
        max_pages: int = MAX_PAGES_DEFAULT,
        default_dpi: float = 150.0,
    ) -> None:
        self.max_pages = max_pages
        self.default_dpi = default_dpi

    def render_pages(
        self,
        file_path: Path,
        media_type: str = "application/pdf",
        max_pages: int | None = None,
        dpi: float | None = None,
    ) -> Generator[RenderedPage, None, None]:
        """Yield rendered pages one at a time for streaming memory efficiency.

        Supports application/pdf and direct image media types.
        Enforces pre-allocation resource bounds (50 pages, 4000 px max dimension, 12 MP max pixels).
        """
        effective_dpi = dpi or self.default_dpi
        page_limit = max_pages or self.max_pages

        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        # Check if direct image file
        lower_name = file_path.name.lower()
        if media_type.startswith("image/") or lower_name.endswith(
            (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp")
        ):
            yield self._load_image_page(file_path, page_number=1, dpi=effective_dpi)
            return

        # PDF rasterization via pypdfium2
        pdf = None
        try:
            try:
                pdf = pdfium.PdfDocument(str(file_path))
            except Exception as exc:
                raise ValueError(
                    f"Failed to parse PDF document for rendering (malformed or invalid structure): {exc}"
                ) from exc

            total_pages = len(pdf)
            if total_pages > page_limit:
                raise ValueError(
                    f"Document page count ({total_pages}) exceeds maximum allowed limit ({page_limit} pages)."
                )

            for page_idx in range(total_pages):
                page_number = page_idx + 1
                page = pdf.get_page(page_idx)
                try:
                    # PDF dimensions in 72-dpi points (page.get_width()/height() accounts for Rotate)
                    pt_width = float(page.get_width())
                    pt_height = float(page.get_height())
                    rotation = int(page.get_rotation()) % 360
                    if rotation not in {0, 90, 180, 270}:
                        rotation = 0

                    scale = effective_dpi / 72.0
                    target_w = int(round(pt_width * scale))
                    target_h = int(round(pt_height * scale))

                    # Strict resource validation BEFORE rendering/allocation
                    if target_w > MAX_PIXEL_DIMENSION or target_h > MAX_PIXEL_DIMENSION:
                        raise ValueError(
                            f"Rendered page dimension ({target_w}x{target_h}) exceeds maximum allowed limit ({MAX_PIXEL_DIMENSION} px)."
                        )
                    if (target_w * target_h) > MAX_TOTAL_PIXELS:
                        raise ValueError(
                            f"Rendered page total pixels ({target_w * target_h}) exceeds maximum allowed limit ({MAX_TOTAL_PIXELS} px)."
                        )

                    # Render to PIL Image
                    pil_image = page.render(scale=scale).to_pil()
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")

                    pixel_w, pixel_h = pil_image.size

                    geometry = PageGeometry(
                        width=pt_width,
                        height=pt_height,
                        rotation=rotation,
                        dpi=effective_dpi,
                    )

                    yield RenderedPage(
                        page_number=page_number,
                        image=pil_image,
                        geometry=geometry,
                        pixel_width=pixel_w,
                        pixel_height=pixel_h,
                    )
                finally:
                    page.close()
        finally:
            if pdf is not None:
                pdf.close()

    def _load_image_page(
        self,
        file_path: Path,
        page_number: int = 1,
        dpi: float = 150.0,
    ) -> RenderedPage:
        """Load single image file as a RenderedPage, enforcing resource bounds before allocation."""
        try:
            with Image.open(file_path) as probe:
                w, h = probe.size
        except Exception as exc:
            raise ValueError(
                f"Failed to parse image file (malformed or unrecognized image format): {exc}"
            ) from exc

        # Strict resource checks on image header dimensions
        if w > MAX_PIXEL_DIMENSION or h > MAX_PIXEL_DIMENSION:
            raise ValueError(
                f"Image dimension ({w}x{h}) exceeds maximum allowed limit ({MAX_PIXEL_DIMENSION} px)."
            )
        if (w * h) > MAX_TOTAL_PIXELS:
            raise ValueError(
                f"Image total pixels ({w * h}) exceeds maximum allowed limit ({MAX_TOTAL_PIXELS} px)."
            )

        with Image.open(file_path) as img:
            rgb_img = img.convert("RGB")

            # Canonical PDF point equivalents (72 pt per inch)
            pt_width = (w * 72.0) / dpi
            pt_height = (h * 72.0) / dpi

            geometry = PageGeometry(
                width=pt_width,
                height=pt_height,
                rotation=0,
                dpi=dpi,
            )

            return RenderedPage(
                page_number=page_number,
                image=rgb_img,
                geometry=geometry,
                pixel_width=w,
                pixel_height=h,
            )
