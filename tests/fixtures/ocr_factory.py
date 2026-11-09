"""Deterministic synthetic test fixtures for OCR and Document Understanding.

Generates synthetic documents covering clean digital text, scanned text,
multi-column layouts, tabular grids, rotated pages, noise, and multilingual samples.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pikepdf
from pikepdf import Array, Dictionary, Name
from PIL import Image, ImageDraw

FIXTURES_DIR = Path(__file__).parent / "ocr"


def _add_paper_texture(img: Image.Image, sigma: float = 2.5, seed: int = 101) -> Image.Image:
    """Add subtle scan/paper texture."""
    arr = np.array(img, dtype=np.float32)
    rng = np.random.RandomState(seed)
    noise = rng.normal(0, sigma, arr.shape)
    noisy = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy)


def create_clean_digital_pdf(path: Path) -> Path:
    """Fixture 1: Clean digital PDF with standard vector text."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    stream_content = (
        b"BT /F2 18 Tf 50 720 Td (ACME AUDIT & FORENSIC SERVICES) Tj ET\n"
        b"BT /F1 12 Tf 50 690 Td (Invoice Number: INV-2026-8801) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (Date: November 9, 2026) Tj ET\n"
        b"BT /F1 12 Tf 50 650 Td (Client: Global DataOps Corporation) Tj ET\n"
        b"BT /F1 11 Tf 50 600 Td (This document contains confidential forensic analysis results.) Tj ET\n"
        b"BT /F1 11 Tf 50 580 Td (All transactions have been verified against banking audit logs.) Tj ET\n"
        b"BT /F1 11 Tf 50 560 Td (Payment is due within thirty days of invoice presentation.) Tj ET\n"
    )

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),  # Standard US Letter
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def create_scanned_printed_text_pdf(path: Path) -> Path:
    """Fixture 2: Scanned printed text with scan grain and imperfect contrast."""
    w, h = 800, 1050
    img = Image.new("RGB", (w, h), color=(248, 246, 240))
    draw = ImageDraw.Draw(img)

    draw.text((60, 60), "STATEMENT OF ACCOUNT", fill=(20, 20, 20))
    draw.text((60, 110), "Account Identifier: ACC-9941-02", fill=(40, 40, 40))
    draw.text((60, 140), "Reporting Period: Q3 2026", fill=(40, 40, 40))
    for i in range(8):
        y = 200 + i * 45
        draw.text(
            (60, y),
            f"Transaction REF-{1000 + i}: Authorized clearing voucher confirmed.",
            fill=(50, 50, 50),
        )
        draw.text((600, y), f"${(i + 1) * 350:.2f}", fill=(30, 30, 30))

    textured = _add_paper_texture(img, sigma=4.0, seed=202)
    path.parent.mkdir(parents=True, exist_ok=True)
    textured.save(path, "PDF", resolution=150.0)
    return path


def create_rotated_pages_pdf(path: Path) -> Path:
    """Fixture 3: 4-page PDF with 0, 90, 180, and 270 degree rotation angles."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    resources = Dictionary(Font=Dictionary(F1=font))

    angles = [0, 90, 180, 270]
    for angle in angles:
        content = (
            f"BT /F1 16 Tf 100 400 Td (Rotation Verification Page: {angle} degrees) Tj ET\n".encode(
                "latin-1"
            )
        )
        page_dict = Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 600, 800]),
            Contents=pdf.make_stream(content),
            Resources=resources,
        )
        if angle != 0:
            page_dict[Name.Rotate] = angle
        pdf.pages.append(pikepdf.Page(page_dict))

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def create_multi_column_pdf(path: Path) -> Path:
    """Fixture 4: Multi-column layout with header and two distinct columns for reading order testing."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    content = (
        # Top banner headline
        b"BT /F2 16 Tf 50 740 Td (EXECUTIVE SUMMARY & JURISDICTIONAL REPORT) Tj ET\n"
        b"BT /F1 10 Tf 50 715 Td (Published by Office of Financial Sanctions Oversight) Tj ET\n"
        # Column 1 (Left)
        b"BT /F2 12 Tf 50 660 Td (Column 1: Regulatory Findings) Tj ET\n"
        b"BT /F1 10 Tf 50 635 Td (The regulatory authority examined corporate disclosures.) Tj ET\n"
        b"BT /F1 10 Tf 50 615 Td (Discrepancies in beneficial ownership were flagged.) Tj ET\n"
        b"BT /F1 10 Tf 50 595 Td (Immediate remediation protocols were mandated.) Tj ET\n"
        # Column 2 (Right)
        b"BT /F2 12 Tf 320 660 Td (Column 2: Compliance Action) Tj ET\n"
        b"BT /F1 10 Tf 320 635 Td (All foreign subsidiary accounts have been restricted.) Tj ET\n"
        b"BT /F1 10 Tf 320 615 Td (Independent monitors were appointed by court decree.) Tj ET\n"
        b"BT /F1 10 Tf 320 595 Td (Final resolution is expected by next statutory audit.) Tj ET\n"
    )

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


def create_table_pdf(path: Path) -> Path:
    """Fixture 5: Structured tabular document with borders, headers, and data cells."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    # Draw table borders and text: 4 columns, 5 rows
    # Col x positions: 50, 180, 310, 440, 560
    # Row y positions: 600, 560, 520, 480, 440, 400
    ops = [
        "BT /F2 16 Tf 50 670 Td (SCHEDULE OF DISBURSEMENTS) Tj ET\n",
        # Horizontal lines
        "0.5 w 50 600 m 560 600 l S\n",
        "0.5 w 50 560 m 560 560 l S\n",
        "0.5 w 50 520 m 560 520 l S\n",
        "0.5 w 50 480 m 560 480 l S\n",
        "0.5 w 50 440 m 560 440 l S\n",
        "0.5 w 50 400 m 560 400 l S\n",
        # Vertical lines
        "0.5 w 50 400 m 50 600 l S\n",
        "0.5 w 180 400 m 180 600 l S\n",
        "0.5 w 310 400 m 310 600 l S\n",
        "0.5 w 440 400 m 440 600 l S\n",
        "0.5 w 560 400 m 560 600 l S\n",
        # Headers
        "BT /F2 11 Tf 60 575 Td (Item Code) Tj ET\n",
        "BT /F2 11 Tf 190 575 Td (Description) Tj ET\n",
        "BT /F2 11 Tf 320 575 Td (Category) Tj ET\n",
        "BT /F2 11 Tf 450 575 Td (Amount USD) Tj ET\n",
        # Row 1
        "BT /F1 10 Tf 60 535 Td (IT-01) Tj ET\n",
        "BT /F1 10 Tf 190 535 Td (Server Hardware) Tj ET\n",
        "BT /F1 10 Tf 320 535 Td (Infrastructure) Tj ET\n",
        "BT /F1 10 Tf 450 535 Td (12,450.00) Tj ET\n",
        # Row 2
        "BT /F1 10 Tf 60 495 Td (SW-02) Tj ET\n",
        "BT /F1 10 Tf 190 495 Td (License Renewal) Tj ET\n",
        "BT /F1 10 Tf 320 495 Td (Software) Tj ET\n",
        "BT /F1 10 Tf 450 495 Td (3,800.00) Tj ET\n",
        # Row 3
        "BT /F1 10 Tf 60 455 Td (CS-03) Tj ET\n",
        "BT /F1 10 Tf 190 455 Td (Security Audit) Tj ET\n",
        "BT /F1 10 Tf 320 455 Td (Professional) Tj ET\n",
        "BT /F1 10 Tf 450 455 Td (7,500.00) Tj ET\n",
        # Row 4
        "BT /F1 10 Tf 60 415 Td (TR-04) Tj ET\n",
        "BT /F1 10 Tf 190 415 Td (Staff Training) Tj ET\n",
        "BT /F1 10 Tf 320 415 Td (Operational) Tj ET\n",
        "BT /F1 10 Tf 450 415 Td (2,150.00) Tj ET\n",
    ]

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream("".join(ops).encode("latin-1")),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def create_mixed_text_images_pdf(path: Path) -> Path:
    """Fixture 6: Document with mixed vector text, table, and embedded raster image."""
    # Create small raster image logo
    logo = Image.new("RGB", (160, 60), color=(220, 230, 245))
    draw = ImageDraw.Draw(logo)
    draw.rectangle([2, 2, 157, 57], outline=(20, 60, 160), width=2)
    draw.text((15, 20), "OFFICIAL LOGO", fill=(20, 40, 140))

    img_buf = io.BytesIO()
    logo.save(img_buf, format="JPEG", quality=95)
    img_data = img_buf.getvalue()

    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )

    # Add image XObject
    img_xobj = pdf.make_stream(img_data)
    img_xobj.Type = Name.XObject
    img_xobj.Subtype = Name.Image
    img_xobj.Width = 160
    img_xobj.Height = 60
    img_xobj.ColorSpace = Name.DeviceRGB
    img_xobj.BitsPerComponent = 8
    img_xobj.Filter = Name.DCTDecode

    resources = Dictionary(
        Font=Dictionary(F1=font, F2=font_bold),
        XObject=Dictionary(Im1=img_xobj),
    )

    ops = (
        b"q 160 0 0 60 50 680 cm /Im1 Do Q\n"
        b"BT /F2 16 Tf 230 710 Td (CERTIFICATE OF INSPECTION) Tj ET\n"
        b"BT /F1 11 Tf 230 685 Td (Verified Identity & Forensic Proof) Tj ET\n"
        b"BT /F1 11 Tf 50 630 Td (This document certifies that the attached visual credentials) Tj ET\n"
        b"BT /F1 11 Tf 50 610 Td (have been verified against registered entity records.) Tj ET\n"
    )

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(ops),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def create_low_res_scan_pdf(path: Path) -> Path:
    """Fixture 7: Low-resolution scan (72 DPI)."""
    w, h = 400, 500
    img = Image.new("RGB", (w, h), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "LOW RESOLUTION SPECIMEN", fill=(0, 0, 0))
    draw.text((20, 50), "Rasterized at 72 DPI display scale.", fill=(30, 30, 30))
    draw.text((20, 80), "Token separation is challenging under coarse sampling.", fill=(50, 50, 50))
    for i in range(4):
        draw.text(
            (20, 130 + i * 30),
            f"Sample line entry {i + 1}: Checkpoint recorded.",
            fill=(40, 40, 40),
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PDF", resolution=72.0)
    return path


def create_noisy_skewed_scan_pdf(path: Path) -> Path:
    """Fixture 8: Noisy scan with rotational skew (2.5 degrees) and lighting gradient."""
    w, h = 800, 1000
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((60, 60), "TAX COMPLIANCE MEMORANDUM", fill=(10, 10, 10))
    draw.text((60, 100), "Assessment Year: 2026-2027", fill=(30, 30, 30))
    draw.text((60, 130), "Taxpayer ID: PANKJ8819A", fill=(30, 30, 30))
    for i in range(6):
        draw.text(
            (60, 180 + i * 35),
            f"Section {40 + i}: Deductions claimed under statutory provisions.",
            fill=(40, 40, 40),
        )

    # Add subtle lighting gradient
    arr = np.array(img, dtype=np.float32)
    gradient = np.linspace(0.85, 1.0, w).reshape(1, w, 1)
    arr = np.clip(arr * gradient, 0, 255).astype(np.uint8)
    graded_img = Image.fromarray(arr)

    # Rotate with slight skew (2.5 deg)
    skewed = graded_img.rotate(
        2.5, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=(255, 255, 255)
    )
    noisy = _add_paper_texture(skewed, sigma=5.0, seed=303)

    path.parent.mkdir(parents=True, exist_ok=True)
    noisy.save(path, "PDF", resolution=150.0)
    return path


def create_multilingual_pdf(path: Path) -> Path:
    """Fixture 9: Multilingual document (English, Spanish, and standard transliterated Indian banking terms)."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    content = (
        b"BT /F2 16 Tf 50 720 Td (MULTILINGUAL CROSS-BORDER NOTIFICATION) Tj ET\n"
        b"BT /F1 11 Tf 50 680 Td (English: Financial statement audited according to international standards.) Tj ET\n"
        b"BT /F1 11 Tf 50 650 Td (Espanol: Estado financiero auditado conforme a las normas internacionales.) Tj ET\n"
        b"BT /F1 11 Tf 50 620 Td (Francais: Etat financier audite selon les normes internationales.) Tj ET\n"
        b"BT /F1 11 Tf 50 590 Td (Indian Banking: IFSC Code SBIN0001234 - Branch Mumbai Fort) Tj ET\n"
        b"BT /F1 11 Tf 50 560 Td (Aadhaar Reference: UIDAI 2345 6789 0123 - KYC Verified) Tj ET\n"
    )

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


def create_scanned_multipage_pdf(path: Path) -> Path:
    """Fixture 10: Multi-page scanned document with multiple sequential pages."""
    w, h = 700, 900
    images = []
    for p in range(2):
        img = Image.new("RGB", (w, h), color=(250, 248, 245))
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), f"SCANNED CONTRACT - PAGE {p + 1}", fill=(20, 20, 20))
        draw.text(
            (50, 100),
            f"Paragraph {p + 1}.1: All terms are strictly enforceable.",
            fill=(40, 40, 40),
        )
        draw.text(
            (50, 140),
            f"Clause {p + 1}.2: Mutual non-disclosure agreement confirmed.",
            fill=(40, 40, 40),
        )
        for i in range(5):
            draw.text(
                (50, 220 + i * 40),
                f"Line item {p * 5 + i + 1}: Certified audited balance.",
                fill=(50, 50, 50),
            )
        textured = _add_paper_texture(img, sigma=3.0, seed=400 + p)
        images.append(textured)

    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=150.0)
    return path


def create_mixed_digital_and_scanned_pdf(path: Path) -> Path:
    """Fixture 11: Mixed document: Page 1 is native digital vector PDF, Page 2 is scanned image."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    # Page 1: Native Digital
    content_p1 = (
        b"BT /F2 16 Tf 50 720 Td (DIGITAL PAGE ONE - CERTIFICATE OF ORIGIN) Tj ET\n"
        b"BT /F1 12 Tf 50 680 Td (Issued By: Federal Trade Directorate) Tj ET\n"
        b"BT /F1 12 Tf 50 650 Td (Status: Certified Digital Clearance) Tj ET\n"
    )
    page1 = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(content_p1),
            Resources=resources,
        )
    )
    pdf.pages.append(page1)

    # Page 2: Scanned Image Page
    img = Image.new("RGB", (612, 792), color=(248, 246, 240))
    draw = ImageDraw.Draw(img)
    draw.text((50, 60), "SCANNED APPENDIX - EXHIBIT B", fill=(20, 20, 20))
    draw.text((50, 110), "Photocopied identification voucher:", fill=(40, 40, 40))
    draw.text((50, 160), "Passport Number: Z8819201", fill=(30, 30, 30))
    textured = _add_paper_texture(img, sigma=3.5, seed=505)

    img_buf = io.BytesIO()
    textured.save(img_buf, format="JPEG", quality=85)
    img_data = img_buf.getvalue()

    image_stream = pdf.make_stream(img_data)
    image_stream.Type = Name.XObject
    image_stream.Subtype = Name.Image
    image_stream.Width = 612
    image_stream.Height = 792
    image_stream.ColorSpace = Name.DeviceRGB
    image_stream.BitsPerComponent = 8
    image_stream.Filter = Name.DCTDecode

    page2_res = Dictionary(XObject=Dictionary(Im1=image_stream))
    content_p2 = b"q 612 0 0 792 0 0 cm /Im1 Do Q\n"
    page2 = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(content_p2),
            Resources=page2_res,
        )
    )
    pdf.pages.append(page2)

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def create_sparse_embedded_text_pdf(path: Path) -> Path:
    """Fixture 12: Scanned image with very sparse vector text (watermark/footer only, <25 chars)."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )

    # Background image containing rich scanned invoice
    img = Image.new("RGB", (612, 792), color=(252, 252, 250))
    draw = ImageDraw.Draw(img)
    draw.text((50, 60), "SCANNED CLEARING INVOICE", fill=(20, 20, 20))
    draw.text((50, 100), "Voucher Amount: $84,500.00", fill=(30, 30, 30))
    draw.text((50, 140), "Beneficiary: ACME Holdings Ltd", fill=(40, 40, 40))
    draw.text((50, 180), "Bank Reference: BK-99410-TX", fill=(40, 40, 40))
    textured = _add_paper_texture(img, sigma=3.0, seed=606)

    img_buf = io.BytesIO()
    textured.save(img_buf, format="JPEG", quality=85)
    img_data = img_buf.getvalue()

    image_stream = pdf.make_stream(img_data)
    image_stream.Type = Name.XObject
    image_stream.Subtype = Name.Image
    image_stream.Width = 612
    image_stream.Height = 792
    image_stream.ColorSpace = Name.DeviceRGB
    image_stream.BitsPerComponent = 8
    image_stream.Filter = Name.DCTDecode

    page_res = Dictionary(Font=Dictionary(F1=font), XObject=Dictionary(Im1=image_stream))
    # Render background image, then overlay sparse 12-char footer text
    content = b"q 612 0 0 792 0 0 cm /Im1 Do Q\nBT /F1 9 Tf 50 30 Td (PAGE 1 OF 1) Tj ET\n"
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(content),
            Resources=page_res,
        )
    )
    pdf.pages.append(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def create_blank_page_pdf(path: Path) -> Path:
    """Fixture 13: Pure blank page."""
    img = Image.new("RGB", (612, 792), color=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PDF", resolution=150.0)
    return path


def create_image_based_table_pdf(path: Path) -> Path:
    """Fixture 14: Scanned/raster image of a bordered table."""
    w, h = 800, 600
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    draw.text((60, 40), "SCHEDULE OF ASSETS", fill=(10, 10, 10))

    # Draw grid table
    row_y = [100, 150, 200, 250, 300]
    col_x = [60, 260, 460, 680]

    for y in row_y:
        draw.line([(60, y), (680, y)], fill=(120, 120, 120), width=2)
    for x in col_x:
        draw.line([(x, 100), (x, 300)], fill=(120, 120, 120), width=2)

    # Headers
    draw.text((80, 115), "Asset Class", fill=(20, 20, 20))
    draw.text((280, 115), "Voucher Code", fill=(20, 20, 20))
    draw.text((480, 115), "Market Valuation", fill=(20, 20, 20))

    # Row 1
    draw.text((80, 165), "Commercial Equity", fill=(40, 40, 40))
    draw.text((280, 165), "EQ-1004", fill=(40, 40, 40))
    draw.text((480, 165), "$1,250,000", fill=(40, 40, 40))

    # Row 2
    draw.text((80, 215), "Sovereign Bonds", fill=(40, 40, 40))
    draw.text((280, 215), "BND-4401", fill=(40, 40, 40))
    draw.text((480, 215), "$850,000", fill=(40, 40, 40))

    # Row 3
    draw.text((80, 265), "Cash Equivalents", fill=(40, 40, 40))
    draw.text((280, 265), "CSH-9912", fill=(40, 40, 40))
    draw.text((480, 265), "$320,000", fill=(40, 40, 40))

    textured = _add_paper_texture(img, sigma=2.0, seed=707)
    path.parent.mkdir(parents=True, exist_ok=True)
    textured.save(path, "PDF", resolution=150.0)
    return path
