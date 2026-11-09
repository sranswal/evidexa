"""Deterministic synthetic PDF test fixture generator."""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name

FIXTURES_DIR = Path(__file__).parent / "pdf"


def _page(pdf: pikepdf.Pdf, content: bytes) -> pikepdf.Page:
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    resources = Dictionary(Font=Dictionary(F1=font))
    page = pikepdf.Page(
        Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, 595, 842]),
            Contents=pdf.make_stream(content),
            Resources=resources,
        )
    )
    pdf.pages.append(page)
    return pdf.pages[-1]


def _text_stream(*lines: str) -> bytes:
    parts = [b"BT /F1 12 Tf", b"0 Tr", b"72 760 Td"]
    for line in lines:
        esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        parts.append(b"(" + esc.encode("latin-1") + b") Tj 0 -16 Td")
    parts.append(b"ET")
    return b"\n".join(parts)


def _pdf_date(dt: datetime) -> str:
    off = dt.utcoffset() or timedelta(0)
    sign = "+" if off >= timedelta(0) else "-"
    mins = abs(int(off.total_seconds() // 60))
    return dt.strftime("D:%Y%m%d%H%M%S") + f"{sign}{mins // 60:02d}'{mins % 60:02d}'"


def build_normal_pdf() -> bytes:
    """Clean single-revision PDF with standard metadata."""
    dt = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    pdf = pikepdf.new()
    _page(pdf, _text_stream("Invoice 2026-001", "Total: 100 SEK"))
    pdf.docinfo["/Producer"] = "Acme Billing 4.2"
    pdf.docinfo["/Creator"] = "Acme ERP"
    pdf.docinfo["/CreationDate"] = _pdf_date(dt)
    pdf.docinfo["/ModDate"] = _pdf_date(dt)
    buf = io.BytesIO()
    pdf.save(buf, compress_streams=False, deterministic_id=True)
    return buf.getvalue()


def build_metadata_variation_pdf() -> bytes:
    """PDF with contradictory dates: ModDate precedes CreationDate."""
    c = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    m = datetime(2025, 1, 1, 8, 0, 0, tzinfo=UTC)  # Prior to creation
    pdf = pikepdf.new()
    _page(pdf, _text_stream("Statement 2026", "Balance: 5000 USD"))
    pdf.docinfo["/Producer"] = "Legacy Custom Tool 1.0"
    pdf.docinfo["/Creator"] = "Unknown Scanner"
    pdf.docinfo["/CreationDate"] = _pdf_date(c)
    pdf.docinfo["/ModDate"] = _pdf_date(m)
    buf = io.BytesIO()
    pdf.save(buf, compress_streams=False, deterministic_id=True)
    return buf.getvalue()


def _append_update(data: bytes, new_objects: dict[int, bytes]) -> bytes:
    prev = int(re.findall(rb"startxref\s+(\d+)\s+%%EOF", data)[-1])
    tail = data[prev:]
    size_match = re.search(rb"/Size\s+(\d+)", tail)
    size = int(size_match.group(1)) if size_match else 10
    root_match = re.search(rb"/Root\s+(\d+\s+\d+\s+R)", tail)
    root = root_match.group(1) if root_match else b"1 0 R"
    info = re.search(rb"/Info\s+(\d+\s+\d+\s+R)", tail)
    out = bytearray(data)
    if not out.endswith(b"\n"):
        out += b"\n"
    offsets = {}
    for num, body in sorted(new_objects.items()):
        offsets[num] = len(out)
        out += b"%d 0 obj\n" % num + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n"
    for num in sorted(offsets):
        out += b"%d 1\n%010d 00000 n \n" % (num, offsets[num])
    new_size = max(size, max(offsets) + 1)
    trailer = b"<< /Size %d /Root %s /Prev %d" % (new_size, root, prev)
    if info:
        trailer += b" /Info " + info.group(1)
    trailer += b" >>"
    out += b"trailer\n" + trailer + b"\nstartxref\n%d\n" % xref + b"%%EOF\n"
    return bytes(out)


def build_incremental_revision_pdf() -> bytes:
    """PDF with 2 revisions where invoice amount was altered from 100 SEK to 900 SEK."""
    base = build_normal_pdf()
    with pikepdf.open(io.BytesIO(base)) as pdf:
        num = pdf.pages[0].obj["/Contents"].objgen[0]

    updated_content = _text_stream("Invoice 2026-001", "Total: 900 SEK")
    stream_obj = (
        b"<< /Length %d >>\nstream\n" % len(updated_content) + updated_content + b"\nendstream"
    )
    return _append_update(base, {num: stream_obj})


def build_structural_anomaly_pdf() -> bytes:
    """PDF containing multiple %%EOF markers and trailing garbage."""
    base = build_normal_pdf()
    return base + b"\n%%EOF\n% extra junk data after nominal end-of-file\n%%EOF\n"


def build_malformed_pdf() -> bytes:
    """Corrupted truncated bytes pretending to be a PDF."""
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nINCOMPLETE_TRUNCATED_STREAM"


def build_wrong_media_type() -> bytes:
    """Plain ASCII text with no PDF header."""
    return b"Hello world! This is a plain text file, definitely not a PDF document.\n"


def build_encrypted_pdf() -> bytes:
    """Password-protected PDF."""
    pdf = pikepdf.new()
    _page(pdf, _text_stream("Secret Classified Financial Report"))
    buf = io.BytesIO()
    pdf.save(
        buf,
        encryption=pikepdf.Encryption(owner="password123", user="password123"),
        compress_streams=False,
    )
    return buf.getvalue()


def generate_all_fixtures() -> dict[str, Path]:
    """Generate all synthetic deterministic fixtures on disk in tests/fixtures/pdf/."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    fixtures = {
        "fixture_normal.pdf": build_normal_pdf(),
        "fixture_metadata_variation.pdf": build_metadata_variation_pdf(),
        "fixture_incremental_revision.pdf": build_incremental_revision_pdf(),
        "fixture_structural_anomaly.pdf": build_structural_anomaly_pdf(),
        "fixture_malformed.pdf": build_malformed_pdf(),
        "fixture_wrong_media_type.txt": build_wrong_media_type(),
        "fixture_encrypted.pdf": build_encrypted_pdf(),
    }

    paths: dict[str, Path] = {}
    for filename, data in fixtures.items():
        dest = FIXTURES_DIR / filename
        dest.write_bytes(data)
        paths[filename] = dest

    return paths


if __name__ == "__main__":
    paths = generate_all_fixtures()
    print(f"Generated {len(paths)} fixtures in {FIXTURES_DIR}")
