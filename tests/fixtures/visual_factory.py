"""Deterministic synthetic test fixtures for Visual Forensics (ELA & Copy-Move).

Generates synthetic images and PDFs with controlled visual tampering artifacts
and benign document features for rigorous false-positive validation.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
import pikepdf
from pikepdf import Array, Dictionary, Name
from PIL import Image, ImageDraw

FIXTURES_DIR = Path(__file__).parent / "visual"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def save_image_as_pdf(image: Image.Image, output_path: Path) -> Path:
    """Save a PIL Image as a single-page PDF document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "PDF", resolution=150.0)
    return output_path


def _add_gaussian_noise(image: Image.Image, sigma: float = 3.0, seed: int = 42) -> Image.Image:
    """Add subtle Gaussian noise to simulate paper scanning noise."""
    arr = np.array(image, dtype=np.float32)
    rng = np.random.RandomState(seed)
    noise = rng.normal(0, sigma, arr.shape)
    noisy = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy)


def _draw_sample_badge(size: int = 100, label: str = "APPROVED", seed: int = 123) -> Image.Image:
    """Create a rich, textured circular emblem/badge with high keypoint density."""
    badge = Image.new("RGB", (size, size), color=(255, 255, 255))
    draw = ImageDraw.Draw(badge)
    draw.ellipse([4, 4, size - 4, size - 4], outline=(160, 20, 20), width=3)
    draw.rectangle(
        [18, 18, size - 18, size - 18], fill=(210, 230, 255), outline=(20, 40, 160), width=2
    )
    draw.line([(10, 10), (size - 10, size - 10)], fill=(20, 120, 40), width=2)
    draw.line([(10, size - 10), (size - 10, 10)], fill=(20, 120, 40), width=2)
    draw.text((22, size // 2 - 8), label, fill=(180, 0, 0))

    badge_np = np.array(badge, dtype=np.int16)
    noise = np.random.RandomState(seed).randint(-15, 15, badge_np.shape)
    textured = np.clip(badge_np + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(textured)


# ---------------------------------------------------------------------------
# ELA Negative Fixtures
# ---------------------------------------------------------------------------


def build_ela_neg_clean_white_text(width: int = 500, height: int = 600) -> Image.Image:
    """Negative Fixture 1: Clean white page with standard invoice text."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), "INVOICE #INV-2026-9041", fill=(10, 10, 10))
    draw.text((40, 70), "Date: November 9, 2026", fill=(40, 40, 40))
    draw.text((40, 100), "Billed To: Acme Legal Corp.", fill=(40, 40, 40))
    for i in range(15):
        y = 150 + i * 25
        draw.text(
            (50, y),
            f"Item {i + 1:02d}: Consulting Services - Module {chr(65 + i)}",
            fill=(60, 60, 60),
        )
        draw.text((380, y), f"${(i + 1) * 125:.2f}", fill=(30, 30, 30))
    draw.line([(40, 540), (460, 540)], fill=(120, 120, 120), width=2)
    draw.text((300, 555), "Total Due: $14,875.00", fill=(10, 10, 10))
    return img


def build_ela_neg_clean_scanned_doc(width: int = 500, height: int = 600) -> Image.Image:
    """Negative Fixture 2: Scanned-document-like image with uniform subtle paper texture."""
    base = build_ela_neg_clean_white_text(width, height)
    return _add_gaussian_noise(base, sigma=3.5, seed=77)


def build_ela_neg_repeated_logos(width: int = 500, height: int = 600) -> Image.Image:
    """Negative Fixture 3: Document with legitimate repeated logo in header and footer."""
    img = build_ela_neg_clean_white_text(width, height)
    logo = _draw_sample_badge(size=60, label="CORP", seed=10)
    img.paste(logo, (420, 30))
    img.paste(logo, (420, 530))
    return img


def build_ela_neg_mixed_content(width: int = 600, height: int = 600) -> Image.Image:
    """Negative Fixture 4: Mixed text, vector graphics bar chart, and photograph block."""
    img = Image.new("RGB", (width, height), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)
    draw.text((40, 30), "Executive Performance Summary", fill=(20, 20, 20))

    # Vector bar chart
    draw.rectangle([40, 80, 300, 260], outline=(150, 150, 150), width=1)
    bar_heights = [60, 110, 95, 140, 120]
    for idx, bh in enumerate(bar_heights):
        bx = 60 + idx * 45
        draw.rectangle([bx, 240 - bh, bx + 30, 240], fill=(70, 120, 200), outline=(20, 50, 120))

    # Synthetic portrait / photo box
    photo = Image.new("RGB", (180, 180), color=(180, 190, 210))
    pdraw = ImageDraw.Draw(photo)
    pdraw.ellipse([40, 30, 140, 130], fill=(230, 200, 180), outline=(100, 80, 60))
    pdraw.rectangle([20, 130, 160, 180], fill=(40, 60, 100))
    photo_noisy = _add_gaussian_noise(photo, sigma=4.0, seed=33)
    img.paste(photo_noisy, (360, 80))

    # Paragraph text
    for i in range(8):
        draw.text(
            (40, 300 + i * 22),
            f"Paragraph row {i}: Q3 metrics demonstrate consistent cross-border performance.",
            fill=(50, 50, 50),
        )
    return img


def build_ela_neg_ordinary_recompression(width: int = 500, height: int = 500) -> Image.Image:
    """Negative Fixture 5: Ordinary single JPEG recompression across entire canvas."""
    base = build_ela_neg_clean_white_text(width, height)
    buf = io.BytesIO()
    base.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def build_ela_neg_legitimate_content_regions(width: int = 600, height: int = 600) -> Image.Image:
    """Negative Fixture 6: Image containing distinct legitimate content regions (header, grid, photo, signature)."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Header block
    draw.rectangle([0, 0, width, 60], fill=(30, 60, 120))
    draw.text((30, 20), "OFFICIAL CERTIFICATE OF CLEARANCE", fill=(255, 255, 255))

    # Data grid
    for r in range(5):
        y = 100 + r * 30
        draw.rectangle([40, y, 560, y + 30], outline=(180, 180, 180))
        draw.text(
            (50, y + 8), f"Section {r + 1}: Verified against registry criteria", fill=(40, 40, 40)
        )

    # Signature line
    draw.line([(350, 450), (550, 450)], fill=(80, 80, 80), width=1)
    draw.text((380, 460), "Authorized Signatory", fill=(80, 80, 80))
    return img


# ---------------------------------------------------------------------------
# ELA Positive Fixtures
# ---------------------------------------------------------------------------


def build_ela_pos_locally_recompressed_patch(width: int = 500, height: int = 500) -> Image.Image:
    """Positive Fixture 1: Base image saved at quality 85; local patch recompressed at quality 40 and spliced back."""
    base = build_ela_neg_clean_white_text(width, height)
    buf_base = io.BytesIO()
    base.save(buf_base, format="JPEG", quality=85)
    buf_base.seek(0)
    base_jpg = Image.open(buf_base).convert("RGB")

    # Cut out local region (140, 180, 320, 280) and recompress at low quality 40
    crop_box = (140, 180, 320, 280)
    patch = base_jpg.crop(crop_box)
    buf_patch = io.BytesIO()
    patch.save(buf_patch, format="JPEG", quality=40)
    buf_patch.seek(0)
    patch_low = Image.open(buf_patch).convert("RGB")

    composite = base_jpg.copy()
    composite.paste(patch_low, (140, 180))
    return composite


def build_ela_pos_different_compression_history(width: int = 500, height: int = 500) -> Image.Image:
    """Positive Fixture 2: Base image saved at quality 55; high-quality patch (quality 98 + noise) inserted."""
    base = build_ela_neg_clean_white_text(width, height)
    buf_base = io.BytesIO()
    base.save(buf_base, format="JPEG", quality=55)
    buf_base.seek(0)
    base_jpg = Image.open(buf_base).convert("RGB")

    # High-quality patch
    pw, ph = 150, 80
    patch = Image.new("RGB", (pw, ph), color=(240, 248, 255))
    pdraw = ImageDraw.Draw(patch)
    pdraw.rectangle([5, 5, pw - 5, ph - 5], outline=(180, 0, 0), width=2)
    pdraw.text((15, 25), "ALTERED AMOUNT: $8,500.00", fill=(180, 0, 0))
    patch_noisy = _add_gaussian_noise(patch, sigma=6.0, seed=99)

    buf_patch = io.BytesIO()
    patch_noisy.save(buf_patch, format="JPEG", quality=98)
    buf_patch.seek(0)
    patch_high = Image.open(buf_patch).convert("RGB")

    composite = base_jpg.copy()
    composite.paste(patch_high, (160, 200))
    return composite


def build_ela_pos_synthetic_composited_boundary(width: int = 500, height: int = 500) -> Image.Image:
    """Positive Fixture 3: Composited image with a sharp synthetic boundary from external source."""
    base = Image.new("RGB", (width, height), color=(245, 245, 245))
    bdraw = ImageDraw.Draw(base)
    for y in range(40, 460, 30):
        bdraw.text((40, y), f"Original baseline ledger entry {y // 30}", fill=(100, 100, 100))

    buf = io.BytesIO()
    base.save(buf, format="JPEG", quality=50)
    buf.seek(0)
    base_jpg = Image.open(buf).convert("RGB")

    # External high-frequency textured stamp
    stamp = _draw_sample_badge(size=120, label="VOID", seed=888)
    composite = base_jpg.copy()
    composite.paste(stamp, (220, 180))
    return composite


# ---------------------------------------------------------------------------
# Copy-Move Negative Fixtures
# ---------------------------------------------------------------------------


def build_cm_neg_repeated_logos(width: int = 600, height: int = 600) -> Image.Image:
    """CM Negative 1: Legitimate repeated corporate logo in header and footer."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 40), "Standard Quarterly Financial Report", fill=(20, 20, 20))
    for i in range(12):
        draw.text(
            (50, 100 + i * 28),
            f"Financial audit statement line {i + 1:02d}: All entries reconciled.",
            fill=(60, 60, 60),
        )

    # Repeated small logo (35 px size, below cluster threshold)
    logo = Image.new("RGB", (35, 35), color=(220, 230, 250))
    ldraw = ImageDraw.Draw(logo)
    ldraw.rectangle([3, 3, 32, 32], outline=(20, 40, 120), width=2)
    ldraw.text((6, 8), "CORP", fill=(20, 40, 120))

    img.paste(logo, (520, 30))
    img.paste(logo, (520, 520))
    return img


def build_cm_neg_repeated_signatures(width: int = 600, height: int = 600) -> Image.Image:
    """CM Negative 2: Repeated signature-like synthetic symbols in two authorized signature blocks."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 40), "Dual Authorization Contract", fill=(20, 20, 20))

    # Stylized signature flourish
    sig = Image.new("RGB", (90, 40), color=(255, 255, 255))
    sdraw = ImageDraw.Draw(sig)
    sdraw.arc([10, 10, 80, 35], 0, 180, fill=(0, 0, 150), width=2)
    sdraw.line([(15, 25), (75, 15)], fill=(0, 0, 150), width=2)

    img.paste(sig, (80, 450))
    img.paste(sig, (380, 450))
    draw.line([(60, 490), (220, 490)], fill=(120, 120, 120))
    draw.line([(360, 490), (520, 490)], fill=(120, 120, 120))
    draw.text((80, 500), "Officer A Signature", fill=(80, 80, 80))
    draw.text((380, 500), "Officer B Signature", fill=(80, 80, 80))
    return img


def build_cm_neg_repeated_stamps(width: int = 600, height: int = 600) -> Image.Image:
    """CM Negative 3: Repeated simple stamps."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    for i in range(10):
        draw.text(
            (50, 80 + i * 30),
            f"Section {i + 1}: Certified authentic verification statement.",
            fill=(50, 50, 50),
        )

    stamp = Image.new("RGB", (45, 45), color=(255, 255, 255))
    sdraw = ImageDraw.Draw(stamp)
    sdraw.ellipse([3, 3, 42, 42], outline=(150, 0, 0), width=2)
    sdraw.text((10, 14), "OK", fill=(150, 0, 0))

    img.paste(stamp, (480, 100))
    img.paste(stamp, (480, 300))
    return img


def build_cm_neg_repeated_text_glyphs(width: int = 600, height: int = 600) -> Image.Image:
    """CM Negative 4: Text-dense document with natural identical words and glyph spacing."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    for row in range(22):
        draw.text(
            (40, 30 + row * 25),
            f"Paragraph {row + 1:02d}: The company acknowledges the receipt of payments and disbursements in full.",
            fill=(40, 40, 40),
        )
    return img


def build_cm_neg_repeated_table_borders(width: int = 600, height: int = 600) -> Image.Image:
    """CM Negative 5: Repeated table cells, lines, and borders."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 30), "Itemized Account Ledger", fill=(20, 20, 20))
    # Draw 8 identical table rows
    for r in range(9):
        y = 70 + r * 45
        draw.line([(40, y), (560, y)], fill=(150, 150, 150), width=1)
    for c in [40, 140, 300, 440, 560]:
        draw.line([(c, 70), (c, 430)], fill=(150, 150, 150), width=1)
    return img


def build_cm_neg_repeated_template_elements(width: int = 600, height: int = 600) -> Image.Image:
    """CM Negative 6: Repeated form headers, footer notices, divider lines."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    for section in range(3):
        sy = 40 + section * 170
        draw.rectangle([40, sy, 560, sy + 30], fill=(230, 235, 245), outline=(100, 120, 160))
        draw.text(
            (50, sy + 7), f"FORM SECTION {section + 1}: APPLICANT DISCLOSURES", fill=(30, 40, 80)
        )
        draw.line([(40, sy + 45), (560, sy + 45)], fill=(180, 180, 180), width=1)
        draw.text(
            (50, sy + 60),
            "Please enter verified details in the provided fields below.",
            fill=(70, 70, 70),
        )
    return img


def build_cm_neg_low_texture(width: int = 600, height: int = 600) -> Image.Image:
    """CM Negative 7: Low-texture page with flat pastel tones and minimal features."""
    img = Image.new("RGB", (width, height), color=(240, 242, 245))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 550, 200], fill=(230, 235, 240))
    draw.rectangle([50, 250, 550, 400], fill=(235, 230, 240))
    return img


def build_cm_neg_ordinary_page(width: int = 600, height: int = 600) -> Image.Image:
    """CM Negative 8: Ordinary document page with diverse unique content and no duplicated patches."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 30), "Confidential Settlement Memorandum", fill=(10, 10, 10))
    draw.rectangle([50, 70, 250, 200], fill=(240, 245, 255), outline=(100, 120, 180))
    draw.ellipse([320, 70, 450, 200], fill=(255, 240, 240), outline=(180, 100, 100))
    draw.polygon([(480, 180), (530, 80), (580, 180)], fill=(240, 255, 240), outline=(80, 160, 80))
    unique_lines = [
        "1. This master agreement is entered into by the designated parties.",
        "2. All official notices must be submitted in writing within ten business days.",
        "3. Proprietary research materials remain the exclusive property of the creator.",
        "4. Standard arbitration rules will apply in the event of unresolved disputes.",
        "5. Final disbursements are scheduled upon completion of audit milestones.",
        "6. Regulatory compliance filings shall be completed prior to next quarter.",
    ]
    for i, line in enumerate(unique_lines):
        draw.text((50, 240 + i * 45), line, fill=(40, 40, 40))
    return img


# ---------------------------------------------------------------------------
# Copy-Move Positive Fixtures
# ---------------------------------------------------------------------------


def build_cm_pos_translated_patch(width: int = 600, height: int = 600) -> Image.Image:
    """CM Positive 1: Rich textured badge at (60, 80) cloned to (360, 320) -> (dx=300, dy=240)."""
    img = build_cm_neg_ordinary_page(width, height)
    badge = _draw_sample_badge(size=100, label="VERIFIED", seed=401)
    img.paste(badge, (60, 80))
    img.paste(badge, (360, 320))
    return img


def build_cm_pos_different_displacement(width: int = 600, height: int = 600) -> Image.Image:
    """CM Positive 2: Cloned patch with different displacement -> (dx=120, dy=340)."""
    img = build_cm_neg_ordinary_page(width, height)
    badge = _draw_sample_badge(size=100, label="OFFICIAL", seed=402)
    img.paste(badge, (80, 60))
    img.paste(badge, (200, 400))  # dx = 120, dy = 340
    return img


def build_cm_pos_mild_rotation(
    width: int = 600, height: int = 600, angle: float = 6.0
) -> Image.Image:
    """CM Positive 3: Cloned patch with mild rotation (6 degrees)."""
    img = build_cm_neg_ordinary_page(width, height)
    badge = _draw_sample_badge(size=100, label="ORIGINAL", seed=403)
    img.paste(badge, (60, 80))

    # Rotated duplicate
    badge_rot = badge.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
    img.paste(badge_rot, (360, 320))
    return img


def build_cm_pos_mild_scaling(
    width: int = 600, height: int = 600, scale: float = 0.9
) -> Image.Image:
    """CM Positive 4: Cloned patch with mild scaling (0.9x)."""
    img = build_cm_neg_ordinary_page(width, height)
    badge = _draw_sample_badge(size=100, label="OFFICIAL", seed=404)
    img.paste(badge, (60, 80))

    new_size = int(100 * scale)
    badge_scaled = badge.resize((new_size, new_size), Image.Resampling.LANCZOS)
    img.paste(badge_scaled, (360, 320))
    return img


def build_cm_pos_multiple_copied_regions(width: int = 700, height: int = 700) -> Image.Image:
    """CM Positive 5: Two distinct cloned patches with two independent displacements."""
    img = build_cm_neg_ordinary_page(width, height)

    # Patch 1: Badge A at (50, 60) cloned to (380, 260) -> dx=330, dy=200
    badge_a = _draw_sample_badge(size=95, label="SEAL_A", seed=501)
    img.paste(badge_a, (50, 60))
    img.paste(badge_a, (380, 260))

    # Patch 2: Badge B at (80, 420) cloned to (420, 480) -> dx=340, dy=60
    badge_b = _draw_sample_badge(size=95, label="STAMP_B", seed=502)
    img.paste(badge_b, (80, 420))
    img.paste(badge_b, (420, 480))

    return img


# ---------------------------------------------------------------------------
# Synthetic PDF Coordinate Fixtures with Known Markers
# ---------------------------------------------------------------------------


def create_synthetic_marker_pdf(
    width_pts: float,
    height_pts: float,
    rotation_deg: int,
    marker_x0: float,
    marker_y0: float,
    marker_w: float,
    marker_h: float,
) -> bytes:
    """Create a single-page PDF with a known red marker rectangle and specified rotation.

    In native PDF bottom-left coordinates:
    Marker is at [marker_x0, marker_y0, marker_x0 + marker_w, marker_y0 + marker_h].
    """
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    resources = Dictionary(Font=Dictionary(F1=font))

    # Stream content drawing the red marker rectangle
    # 'q 1 0 0 rg x y w h re f Q'
    content = (
        f"q 1 0 0 rg {marker_x0:.2f} {marker_y0:.2f} {marker_w:.2f} {marker_h:.2f} re f Q\n"
        f"BT /F1 12 Tf 0 0 0 rg 50 50 Td (Rotation Test Page: {rotation_deg} deg) Tj ET\n"
    ).encode("latin-1")

    page_dict = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, width_pts, height_pts]),
        Contents=pdf.make_stream(content),
        Resources=resources,
    )
    if rotation_deg != 0:
        page_dict[Name.Rotate] = rotation_deg

    pdf.pages.append(pikepdf.Page(page_dict))

    buf = io.BytesIO()
    pdf.save(buf, compress_streams=False, deterministic_id=True)
    return buf.getvalue()


def build_clean_image(width: int = 400, height: int = 400) -> Image.Image:
    """Clean synthetic document image with unique shapes and text, no duplicate elements."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "Authentic Invoice Document", fill=(0, 0, 0))
    draw.text((20, 50), "Payee: Clean Organization", fill=(50, 50, 50))
    draw.rectangle([50, 100, 150, 180], fill=(200, 220, 240), outline=(0, 0, 0))
    draw.ellipse([220, 100, 320, 200], fill=(240, 200, 220), outline=(0, 0, 0))
    return img


# Legacy aliases for compatibility with previous test suites
build_ela_spliced_image = build_ela_pos_different_compression_history
build_copy_move_image = build_cm_pos_translated_patch


def get_or_create_fixture(name: str, factory_fn: Any, as_pdf: bool = False) -> Path:
    """Retrieve existing fixture path or deterministically generate it."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".pdf" if as_pdf else ".png"
    target = FIXTURES_DIR / f"{name}{ext}"

    if not target.exists():
        img = factory_fn()
        if as_pdf:
            save_image_as_pdf(img, target)
        else:
            img.save(target)

    return target
