"""Deterministic Multilingual E2E Evaluation Corpus for EVIDEXA Phase 4D.3.7.

Generates 10 distinct synthetic forensic document fixtures covering:
1. English digital invoice (vector text).
2. Hindi scanned invoice (Devanagari OCR).
3. Mixed Hindi-English invoice (Bilingual OCR).
4. English and Hindi receipts (Receipt schema).
5. Bank statement with Devanagari numerals (PII masking & numeral conversion).
6. Hybrid PDF with vector text and embedded scanned content (Geometry routing & dual-layer).
7. Poor-quality scanned document (Degraded text & uncertainty handling).
8. Duplicate document (Upload deduplication & hash verification).
9. Conflicting amounts document (Cross-document inconsistency & findings).
10. Unsupported-script document (Cyrillic script limitation handling).

All corporate entities, individual names, amounts, account numbers, and references are 100% synthetic.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pikepdf
from pikepdf import Array, Dictionary, Name
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_INDIC = (
    "C:/Windows/Fonts/Nirmala.ttc" if os.path.exists("C:/Windows/Fonts/Nirmala.ttc") else None
)
FONT_LATIN = "C:/Windows/Fonts/arial.ttf" if os.path.exists("C:/Windows/Fonts/arial.ttf") else None


@dataclass
class CorpusFixtureMeta:
    fixture_id: str
    filename: str
    doc_type: str
    primary_script: str
    expected_routing: str
    expected_text_snippets: list[str]
    expected_fields: dict[str, Any]
    known_limitations: str
    provenance: str = "Synthetic deterministic forensic generator"


def _get_font(size: int = 22, indic: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = FONT_INDIC if indic else FONT_LATIN
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _add_texture_and_noise(img: Image.Image, sigma: float = 2.0, seed: int = 42) -> Image.Image:
    """Add subtle scan grain and texture."""
    arr = np.array(img, dtype=np.float32)
    rng = np.random.RandomState(seed)
    noise = rng.normal(0, sigma, arr.shape)
    noisy = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy)


def _image_to_pdf(img: Image.Image, out_path: Path) -> Path:
    """Save PIL Image as deterministic single-page PDF."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PDF", resolution=150.0)
    return out_path


# -----------------------------------------------------------------------------
# Fixture 1: English Digital Invoice
# -----------------------------------------------------------------------------
def create_fixture_english_digital_invoice(path: Path) -> Path:
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    stream_content = (
        b"BT /F2 18 Tf 50 720 Td (INVOICE - APEX TECHNICAL CONSULTING) Tj ET\n"
        b"BT /F1 12 Tf 50 690 Td (Invoice Number: INV-EN-1001) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (Invoice Date: 2026-11-10) Tj ET\n"
        b"BT /F1 12 Tf 50 650 Td (Vendor: Apex Technical Consulting Ltd) Tj ET\n"
        b"BT /F1 12 Tf 50 630 Td (Buyer: Global DataOps Corporation) Tj ET\n"
        b"BT /F2 14 Tf 50 580 Td (Total Amount: $12,500.00 USD) Tj ET\n"
        b"BT /F1 10 Tf 50 540 Td (Payment Terms: Net 30 days) Tj ET\n"
    )

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


# -----------------------------------------------------------------------------
# Fixture 2: Hindi Scanned Invoice
# -----------------------------------------------------------------------------
def create_fixture_hindi_scanned_invoice(path: Path) -> Path:
    w, h = 900, 1200
    img = Image.new("RGB", (w, h), color=(252, 250, 246))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(32, indic=True)
    f_body = _get_font(24, indic=True)
    f_bold = _get_font(26, indic=True)

    draw.text((80, 80), "कर बीजक", fill=(10, 10, 10), font=f_title)
    draw.text((80, 150), "बीजक संख्या: INV-HI-4001", fill=(30, 30, 30), font=f_bold)
    draw.text((80, 200), "दिनांक: 2026-11-10", fill=(40, 40, 40), font=f_body)
    draw.text((80, 250), "विक्रेता: मेसर्स भारत एंटरप्राइजेज", fill=(40, 40, 40), font=f_body)
    draw.text((80, 300), "क्रेता: ग्लोबल डेटाऑप्स कॉर्पोरेशन", fill=(40, 40, 40), font=f_body)
    draw.text((80, 360), "विवरण: फोरेंसिक सुरक्षा परामर्श एवं ऑडिट", fill=(40, 40, 40), font=f_body)
    draw.text((80, 440), "कुल राशि: ₹१२,५००.००", fill=(10, 10, 10), font=f_bold)
    draw.text((80, 500), "भुगतान स्थिति: लंबित (Due 30 Days)", fill=(50, 50, 50), font=f_body)

    textured = _add_texture_and_noise(img, sigma=2.5, seed=101)
    return _image_to_pdf(textured, path)


# -----------------------------------------------------------------------------
# Fixture 3: Mixed Hindi-English Invoice
# -----------------------------------------------------------------------------
def create_fixture_mixed_hindi_english_invoice(path: Path) -> Path:
    w, h = 900, 1200
    img = Image.new("RGB", (w, h), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(30, indic=True)
    f_body = _get_font(22, indic=True)
    f_bold = _get_font(24, indic=True)

    draw.text((80, 80), "TAX INVOICE / कर बीजक", fill=(10, 10, 10), font=f_title)
    draw.text((80, 140), "Invoice Number / बीजक सं: INV-MIX-5001", fill=(20, 20, 20), font=f_bold)
    draw.text((80, 190), "Date / दिनांक: 2026-11-10", fill=(30, 30, 30), font=f_body)
    draw.text((80, 240), "Vendor / विक्रेता: Apex भारत Ltd", fill=(30, 30, 30), font=f_body)
    draw.text((80, 290), "GSTIN / जीएसटी: 07AAAAA0000A1Z5", fill=(30, 30, 30), font=f_bold)
    draw.text((80, 350), "Description: Enterprise Forensic Audit", fill=(40, 40, 40), font=f_body)
    draw.text((80, 420), "Total Amount / कुल राशि: ₹12,500.00", fill=(10, 10, 10), font=f_bold)

    textured = _add_texture_and_noise(img, sigma=2.0, seed=102)
    return _image_to_pdf(textured, path)


# -----------------------------------------------------------------------------
# Fixture 4A: English Receipt
# -----------------------------------------------------------------------------
def create_fixture_english_receipt(path: Path) -> Path:
    w, h = 800, 1050
    img = Image.new("RGB", (w, h), color=(248, 246, 240))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(28, indic=False)
    f_body = _get_font(20, indic=False)
    f_bold = _get_font(22, indic=False)

    draw.text((70, 70), "OFFICIAL PAYMENT RECEIPT", fill=(10, 10, 10), font=f_title)
    draw.text((70, 130), "Receipt Number: REC-EN-1001", fill=(30, 30, 30), font=f_bold)
    draw.text((70, 170), "Reference Invoice: INV-EN-1001", fill=(40, 40, 40), font=f_body)
    draw.text((70, 210), "Merchant: Apex Technical Consulting Ltd", fill=(40, 40, 40), font=f_body)
    draw.text((70, 250), "Date: 2026-11-12", fill=(40, 40, 40), font=f_body)
    draw.text((70, 310), "Amount Received: $12,500.00 USD", fill=(10, 10, 10), font=f_bold)
    draw.text((70, 360), "Payment Method: Wire Transfer", fill=(50, 50, 50), font=f_body)

    textured = _add_texture_and_noise(img, sigma=2.5, seed=103)
    return _image_to_pdf(textured, path)


# -----------------------------------------------------------------------------
# Fixture 4B: Hindi Receipt
# -----------------------------------------------------------------------------
def create_fixture_hindi_receipt(path: Path) -> Path:
    w, h = 800, 1050
    img = Image.new("RGB", (w, h), color=(250, 248, 242))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(28, indic=True)
    f_body = _get_font(20, indic=True)
    f_bold = _get_font(22, indic=True)

    draw.text((70, 70), "भुगतान रसीद", fill=(10, 10, 10), font=f_title)
    draw.text((70, 130), "रसीद क्रमांक: REC-HI-4001", fill=(30, 30, 30), font=f_bold)
    draw.text((70, 170), "संदर्भ बीजक: INV-HI-4001", fill=(40, 40, 40), font=f_body)
    draw.text((70, 210), "प्राप्तकर्ता: मेसर्स भारत एंटरप्राइजेज", fill=(40, 40, 40), font=f_body)
    draw.text((70, 250), "दिनांक: 2026-11-12", fill=(40, 40, 40), font=f_body)
    draw.text((70, 310), "प्राप्त धनराशि: ₹१२,५००.००", fill=(10, 10, 10), font=f_bold)
    draw.text((70, 360), "माध्यम: बैंक ट्रांसफर (NEFT/RTGS)", fill=(50, 50, 50), font=f_body)

    textured = _add_texture_and_noise(img, sigma=2.5, seed=104)
    return _image_to_pdf(textured, path)


# -----------------------------------------------------------------------------
# Fixture 5: Bank Statement with Devanagari Numerals & PII
# -----------------------------------------------------------------------------
def create_fixture_bank_statement_devanagari(path: Path) -> Path:
    w, h = 900, 1200
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(30, indic=True)
    f_body = _get_font(22, indic=True)
    f_bold = _get_font(24, indic=True)

    draw.text((80, 80), "भारतीय स्टेट बैंक", fill=(10, 10, 10), font=f_title)
    draw.text((80, 140), "खाता विवरणी (Bank Statement)", fill=(30, 30, 30), font=f_bold)
    draw.text((80, 190), "खाता संख्या: १२३४५६७८९०१२", fill=(20, 20, 20), font=f_bold)
    draw.text((80, 240), "खाताधारक: मेसर्स भारत एंटरप्राइजेज", fill=(40, 40, 40), font=f_body)
    draw.text((80, 290), "अवधि: नवंबर 2026", fill=(40, 40, 40), font=f_body)
    draw.text(
        (80, 350), "दिनांक       विवरण                        राशि", fill=(30, 30, 30), font=f_bold
    )
    draw.text(
        (80, 400), "2026-11-12  जमा - REC-HI-4001     +₹१२,५००.००", fill=(40, 40, 40), font=f_body
    )
    draw.text((80, 470), "अंतिम शेष (Ending Balance): ₹१,४८,५००.००", fill=(10, 10, 10), font=f_bold)

    textured = _add_texture_and_noise(img, sigma=2.0, seed=105)
    return _image_to_pdf(textured, path)


# -----------------------------------------------------------------------------
# Fixture 6: Hybrid PDF (Vector Header + Embedded Scanned Receipt)
# -----------------------------------------------------------------------------
def create_fixture_hybrid_vector_raster(path: Path) -> Path:
    # 1. Create raster scanned receipt image (takes up bottom 65% of page)
    w_px, h_px = 700, 700
    img = Image.new("RGB", (w_px, h_px), color=(246, 244, 238))
    draw = ImageDraw.Draw(img)
    f_bold = _get_font(24, indic=True)
    f_body = _get_font(20, indic=True)

    draw.text((40, 40), "भुगतान चालान / PAYMENT SLIP", fill=(20, 20, 20), font=f_bold)
    draw.text((40, 90), "रसीद सं: SLIP-HYB-7001", fill=(30, 30, 30), font=f_body)
    draw.text((40, 140), "विक्रेता: मेसर्स भारत एंटरप्राइजेज", fill=(40, 40, 40), font=f_body)
    draw.text((40, 200), "स्वीकृत राशि: ₹१२,५००.००", fill=(10, 10, 10), font=f_bold)
    textured = _add_texture_and_noise(img, sigma=3.0, seed=106)

    img_byte_arr = io.BytesIO()
    textured.save(img_byte_arr, format="JPEG", quality=85)
    img_bytes = img_byte_arr.getvalue()

    # 2. Construct PDF with vector header and embedded image
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font))

    image_obj = pdf.make_stream(img_bytes)
    image_obj.Type = Name.XObject
    image_obj.Subtype = Name.Image
    image_obj.Width = w_px
    image_obj.Height = h_px
    image_obj.ColorSpace = Name.DeviceRGB
    image_obj.BitsPerComponent = 8
    image_obj.Filter = Name.DCTDecode
    resources.XObject = Dictionary(Im1=image_obj)

    page_w, page_h = 612, 792
    img_render_w = 512
    img_render_h = 450
    img_x = 50
    img_y = 60

    # Stream: Vector text in header, then image
    stream = (
        f"BT /F1 16 Tf 50 720 Td (EVIDEXA FORENSIC AUDIT DISCLOSURE) Tj ET\n"
        f"BT /F1 11 Tf 50 690 Td (Vector audit header: Certified hybrid test record 2026) Tj ET\n"
        f"q {img_render_w} 0 0 {img_render_h} {img_x} {img_y} cm /Im1 Do Q\n"
    ).encode()

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, page_w, page_h]),
        Contents=pdf.make_stream(stream),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


# -----------------------------------------------------------------------------
# Fixture 7: Poor-Quality Degraded Scanned Document
# -----------------------------------------------------------------------------
def create_fixture_poor_quality_scan(path: Path) -> Path:
    w, h = 600, 800
    img = Image.new("RGB", (w, h), color=(235, 230, 220))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(22, indic=True)
    f_body = _get_font(18, indic=True)

    draw.text((50, 60), "धुंधला चालान वाउचर", fill=(70, 70, 70), font=f_title)
    draw.text((50, 110), "वाउचर सं: VOUCH-POOR-8001", fill=(80, 80, 80), font=f_body)
    draw.text((50, 160), "देय राशि: ₹४,५००.००", fill=(70, 70, 70), font=f_body)

    # Apply heavy noise and blur
    noisy = _add_texture_and_noise(img, sigma=8.0, seed=107)
    blurred = noisy.filter(ImageFilter.GaussianBlur(radius=0.8))
    # Rotate slightly (-2.5 deg)
    rotated = blurred.rotate(-2.5, resample=Image.BICUBIC, expand=False, fillcolor=(235, 230, 220))
    return _image_to_pdf(rotated, path)


# -----------------------------------------------------------------------------
# Fixture 8: Duplicate Document (Re-uses bytes of Fixture 1)
# -----------------------------------------------------------------------------
def create_fixture_duplicate_invoice(path: Path, source_path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source_path.read_bytes())
    return path


# -----------------------------------------------------------------------------
# Fixture 9: Conflicting Document (Discrepancy: Amount 11,000.00 vs 12,500.00)
# -----------------------------------------------------------------------------
def create_fixture_conflicting_receipt(path: Path) -> Path:
    w, h = 800, 1050
    img = Image.new("RGB", (w, h), color=(250, 248, 242))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(28, indic=True)
    f_body = _get_font(20, indic=True)
    f_bold = _get_font(22, indic=True)

    draw.text((70, 70), "विवादित भुगतान रसीद", fill=(10, 10, 10), font=f_title)
    draw.text((70, 130), "रसीद क्रमांक: REC-DISCREPANT-9001", fill=(30, 30, 30), font=f_bold)
    draw.text((70, 170), "संदर्भ बीजक: INV-HI-4001", fill=(40, 40, 40), font=f_body)
    draw.text((70, 210), "विक्रेता: मेसर्स भारत एंटरप्राइजेज", fill=(40, 40, 40), font=f_body)
    draw.text((70, 250), "दिनांक: 2026-11-12", fill=(40, 40, 40), font=f_body)
    # Intentional discrepancy: 11,000.00 vs 12,500.00
    draw.text((70, 310), "प्राप्त धनराशि: ₹११,०००.००", fill=(10, 10, 10), font=f_bold)
    draw.text((70, 360), "अंतर टिप्पणी: आंशिक भुगतान", fill=(50, 50, 50), font=f_body)

    textured = _add_texture_and_noise(img, sigma=2.0, seed=108)
    return _image_to_pdf(textured, path)


# -----------------------------------------------------------------------------
# Fixture 10: Unsupported Script (Cyrillic Script)
# -----------------------------------------------------------------------------
def create_fixture_unsupported_script(path: Path) -> Path:
    w, h = 800, 1000
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(26, indic=False)
    f_body = _get_font(20, indic=False)

    draw.text((70, 70), "Счет-фактура № 1042", fill=(10, 10, 10), font=f_title)
    draw.text((70, 130), "Поставщик: ООО Северный Аудит", fill=(30, 30, 30), font=f_body)
    draw.text((70, 180), "Дата: 2026-11-10", fill=(40, 40, 40), font=f_body)
    draw.text((70, 240), "Итоговая сумма: 50000 руб", fill=(10, 10, 10), font=f_body)

    textured = _add_texture_and_noise(img, sigma=2.0, seed=109)
    return _image_to_pdf(textured, path)


# -----------------------------------------------------------------------------
# Corpus Metadata Manifest
# -----------------------------------------------------------------------------
CORPUS_MANIFEST: list[CorpusFixtureMeta] = [
    CorpusFixtureMeta(
        fixture_id="FIX_01_EN_DIGITAL_INV",
        filename="english_digital_invoice.pdf",
        doc_type="INVOICE",
        primary_script="LATIN",
        expected_routing="VECTOR_ONLY",
        expected_text_snippets=["INV-EN-1001", "Apex Technical", "12,500.00"],
        expected_fields={"invoice_number": "INV-EN-1001", "total_amount": 12500.0},
        known_limitations="Clean vector text; no OCR required.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_02_HI_SCANNED_INV",
        filename="hindi_scanned_invoice.pdf",
        doc_type="INVOICE",
        primary_script="DEVANAGARI",
        expected_routing="OCR_ONLY",
        expected_text_snippets=["बीजक", "भारत"],
        expected_fields={"total_amount": 12500.0},
        known_limitations="Requires PP-OCRv5 Devanagari model with unclip ratio 1.6.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_03_MIXED_HI_EN_INV",
        filename="mixed_hindi_english_invoice.pdf",
        doc_type="INVOICE",
        primary_script="MIXED",
        expected_routing="OCR_ONLY",
        expected_text_snippets=["TAX INVOICE", "कर बीजक", "07AAAAA0000A1Z5"],
        expected_fields={"gstin": "07AAAAA0000A1Z5"},
        known_limitations="Mixed-script alphanumeric identifiers; must preserve Latin digits.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_04A_EN_RECEIPT",
        filename="english_receipt.pdf",
        doc_type="RECEIPT",
        primary_script="LATIN",
        expected_routing="OCR_ONLY",
        expected_text_snippets=["REC-EN-1001", "12,500.00"],
        expected_fields={"receipt_number": "REC-EN-1001"},
        known_limitations="Scanned receipt; RapidOCR Latin recognition.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_04B_HI_RECEIPT",
        filename="hindi_receipt.pdf",
        doc_type="RECEIPT",
        primary_script="DEVANAGARI",
        expected_routing="OCR_ONLY",
        expected_text_snippets=["भुगतान रसीद", "REC-HI-4001"],
        expected_fields={"receipt_number": "REC-HI-4001"},
        known_limitations="Devanagari OCR; numeral conversion.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_05_BANK_STMT_DEV",
        filename="bank_statement_devanagari.pdf",
        doc_type="BANK_STATEMENT",
        primary_script="DEVANAGARI",
        expected_routing="OCR_ONLY",
        expected_text_snippets=["भारतीय स्टेट बैंक", "खाता संख्या"],
        expected_fields={"account_number_masked": "****9012"},
        known_limitations="Devanagari digits १२३४५६७८९०१२ must be masked to ****9012.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_06_HYBRID_VEC_RAST",
        filename="hybrid_vector_raster.pdf",
        doc_type="RECEIPT",
        primary_script="MIXED",
        expected_routing="HYBRID_FUSION",
        expected_text_snippets=["EVIDEXA FORENSIC AUDIT", "भुगतान चालान"],
        expected_fields={},
        known_limitations="Vector header + raster body; PDFium text must be retained in alternative layers.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_07_POOR_QUALITY_SCAN",
        filename="poor_quality_scan.pdf",
        doc_type="UNKNOWN",
        primary_script="DEVANAGARI",
        expected_routing="OCR_ONLY",
        expected_text_snippets=["वाउचर"],
        expected_fields={},
        known_limitations="High noise and blur; character confidence uncalibrated; potential uncertainty flags.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_08_DUPLICATE_INV",
        filename="duplicate_invoice.pdf",
        doc_type="INVOICE",
        primary_script="LATIN",
        expected_routing="VECTOR_ONLY",
        expected_text_snippets=["INV-EN-1001"],
        expected_fields={"invoice_number": "INV-EN-1001"},
        known_limitations="Identical SHA-256 to Fixture 1; tests idempotency and deduplication.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_09_CONFLICTING_DOC",
        filename="conflicting_receipt.pdf",
        doc_type="RECEIPT",
        primary_script="DEVANAGARI",
        expected_routing="OCR_ONLY",
        expected_text_snippets=["REC-DISCREPANT-9001", "११,०००.००"],
        expected_fields={"total_amount": 11000.0},
        known_limitations="Amount discrepancy vs invoice (11,000.00 vs 12,500.00); triggers consistency finding.",
    ),
    CorpusFixtureMeta(
        fixture_id="FIX_10_UNSUPPORTED_SCRIPT",
        filename="unsupported_script.pdf",
        doc_type="UNKNOWN",
        primary_script="CYRILLIC",
        expected_routing="OCR_ONLY",
        expected_text_snippets=[],
        expected_fields={},
        known_limitations="Cyrillic script is not supported in Phase 4D; must handle gracefully without crashing.",
    ),
]
