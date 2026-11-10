"""PDF Dossier Exporter.

Renders an InvestigationDossier to a multi-page, deterministic PDF document
with EVIDEXA branding, structured chapters, table formatting, and explicit legal disclaimers.
Uses pikepdf for reproducible vector PDF generation without external dependencies.
"""

from __future__ import annotations

import io
import textwrap

import pikepdf

from document_intelligence.domain.models.investigation_dossier import InvestigationDossier


def _escape_pdf(text: str) -> str:
    """Escape special characters for PDF literal strings."""
    sanitized = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return sanitized.encode("latin-1", "replace").decode("latin-1")


class _PdfCanvas:
    """Helper for constructing multi-page PDF documents with pikepdf."""

    PAGE_WIDTH = 612.0
    PAGE_HEIGHT = 792.0
    MARGIN_LEFT = 50.0
    MARGIN_RIGHT = 562.0
    MARGIN_TOP = 730.0
    MARGIN_BOTTOM = 55.0

    def __init__(self, pdf: pikepdf.Pdf) -> None:
        self.pdf = pdf
        self.pages: list[tuple[pikepdf.Page, list[str]]] = []
        self.current_stream: list[str] = []
        self.current_y = self.MARGIN_TOP

        # Shared fonts
        self.font_regular = self.pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Font,
                Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica,
            )
        )
        self.font_bold = self.pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Font,
                Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica_Bold,
            )
        )
        self.font_oblique = self.pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Font,
                Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica_Oblique,
            )
        )

        self.new_page()

    def new_page(self) -> None:
        """Start a new blank page with header."""
        page = self.pdf.add_blank_page(page_size=(self.PAGE_WIDTH, self.PAGE_HEIGHT))
        page.Resources = pikepdf.Dictionary(
            Font=pikepdf.Dictionary(
                F1=self.font_regular,
                F2=self.font_bold,
                F3=self.font_oblique,
            )
        )
        self.current_stream = []
        self.pages.append((page, self.current_stream))
        self.current_y = self.MARGIN_TOP

        # Draw running header on every page
        header_text = _escape_pdf("EVIDEXA | AI-Powered Digital Forensics & Document Intelligence")
        self.current_stream.append(
            f"BT /F2 8 Tf 0.3 0.3 0.3 rg {self.MARGIN_LEFT:.1f} 760 Td ({header_text}) Tj ET\n"
        )
        self.current_stream.append(
            f"0.5 w 0.8 0.8 0.8 RG {self.MARGIN_LEFT:.1f} 752 m {self.MARGIN_RIGHT:.1f} 752 l S\n"
        )

    def ensure_space(self, height: float) -> None:
        """Ensure vertical space exists on current page; otherwise trigger a new page."""
        if self.current_y - height < self.MARGIN_BOTTOM:
            self.new_page()

    def add_title(self, text: str) -> None:
        """Add main document title."""
        self.ensure_space(36.0)
        esc = _escape_pdf(text)
        self.current_stream.append(
            f"BT /F2 18 Tf 0.05 0.1 0.25 rg {self.MARGIN_LEFT:.1f} {self.current_y:.1f} Td ({esc}) Tj ET\n"
        )
        self.current_y -= 26.0

    def add_section_heading(self, text: str) -> None:
        """Add numbered chapter/section heading."""
        self.ensure_space(32.0)
        esc = _escape_pdf(text)
        self.current_y -= 10.0
        # Background bar
        self.current_stream.append(
            f"0.92 0.94 0.96 rg {self.MARGIN_LEFT:.1f} {self.current_y - 4:.1f} {self.MARGIN_RIGHT - self.MARGIN_LEFT:.1f} 18 re f\n"
        )
        self.current_stream.append(
            f"BT /F2 11 Tf 0.1 0.2 0.4 rg {self.MARGIN_LEFT + 6:.1f} {self.current_y:.1f} Td ({esc}) Tj ET\n"
        )
        self.current_y -= 20.0

    def add_subheading(self, text: str) -> None:
        """Add subsection heading."""
        self.ensure_space(20.0)
        esc = _escape_pdf(text)
        self.current_stream.append(
            f"BT /F2 10 Tf 0.15 0.15 0.15 rg {self.MARGIN_LEFT:.1f} {self.current_y:.1f} Td ({esc}) Tj ET\n"
        )
        self.current_y -= 15.0

    def add_paragraph(
        self, text: str, font: str = "F1", size: float = 9.0, indent: float = 0.0
    ) -> None:
        """Add wrapped paragraph text."""
        lines = []
        for raw_line in text.split("\n"):
            if not raw_line.strip():
                lines.append("")
                continue
            wrapped = textwrap.wrap(raw_line, width=82)
            lines.extend(wrapped)

        line_height = size * 1.35
        for line in lines:
            if not line:
                self.ensure_space(line_height * 0.6)
                self.current_y -= line_height * 0.6
                continue
            self.ensure_space(line_height)
            esc = _escape_pdf(line)
            x = self.MARGIN_LEFT + indent
            self.current_stream.append(
                f"BT /{font} {size:.1f} Tf 0.1 0.1 0.1 rg {x:.1f} {self.current_y:.1f} Td ({esc}) Tj ET\n"
            )
            self.current_y -= line_height

    def add_bullet(self, text: str) -> None:
        """Add bullet point line."""
        wrapped = textwrap.wrap(text, width=78)
        line_height = 12.0
        for i, line in enumerate(wrapped):
            self.ensure_space(line_height)
            esc = _escape_pdf(line)
            bullet = "\\225 " if i == 0 else "  "
            x = self.MARGIN_LEFT + 12.0
            self.current_stream.append(
                f"BT /F1 9 Tf 0.15 0.15 0.15 rg {x:.1f} {self.current_y:.1f} Td ({bullet}{esc}) Tj ET\n"
            )
            self.current_y -= line_height

    def add_key_value(self, key: str, value: str) -> None:
        """Add a two-column key-value attribute row."""
        self.ensure_space(14.0)
        esc_k = _escape_pdf(key)
        esc_v = _escape_pdf(value)
        self.current_stream.append(
            f"BT /F2 9 Tf 0.2 0.2 0.2 rg {self.MARGIN_LEFT:.1f} {self.current_y:.1f} Td ({esc_k}:) Tj ET\n"
        )
        self.current_stream.append(
            f"BT /F1 9 Tf 0.1 0.1 0.1 rg {self.MARGIN_LEFT + 130.0:.1f} {self.current_y:.1f} Td ({esc_v}) Tj ET\n"
        )
        self.current_y -= 13.0

    def add_disclaimer_box(self, disclaimer_text: str) -> None:
        """Add a styled callout box for legal disclaimer."""
        wrapped = textwrap.wrap(disclaimer_text, width=75)
        box_height = len(wrapped) * 12.0 + 26.0
        self.ensure_space(box_height + 10.0)

        box_y = self.current_y - box_height
        box_w = self.MARGIN_RIGHT - self.MARGIN_LEFT

        # Box background and border
        self.current_stream.append(
            f"0.98 0.96 0.92 rg 0.7 0.5 0.2 RG 0.8 w {self.MARGIN_LEFT:.1f} {box_y:.1f} {box_w:.1f} {box_height:.1f} re B\n"
        )
        # Header inside box
        hdr = _escape_pdf("IMPORTANT LEGAL & EVIDENTIARY DISCLAIMER")
        self.current_stream.append(
            f"BT /F2 9 Tf 0.6 0.3 0.0 rg {self.MARGIN_LEFT + 10.0:.1f} {self.current_y - 14.0:.1f} Td ({hdr}) Tj ET\n"
        )

        cur_text_y = self.current_y - 26.0
        for line in wrapped:
            esc = _escape_pdf(line)
            self.current_stream.append(
                f"BT /F1 8.5 Tf 0.2 0.2 0.2 rg {self.MARGIN_LEFT + 10.0:.1f} {cur_text_y:.1f} Td ({esc}) Tj ET\n"
            )
            cur_text_y -= 11.0

        self.current_y -= box_height + 14.0

    def add_divider(self) -> None:
        """Add a thin horizontal divider line."""
        self.ensure_space(10.0)
        self.current_stream.append(
            f"0.3 w 0.8 0.8 0.8 RG {self.MARGIN_LEFT:.1f} {self.current_y:.1f} m {self.MARGIN_RIGHT:.1f} {self.current_y:.1f} l S\n"
        )
        self.current_y -= 10.0

    def finalize(self, dossier_id: str) -> bytes:
        """Append footers with total page numbers and encode PDF bytes."""
        total_pages = len(self.pages)
        for idx, (page, stream) in enumerate(self.pages, start=1):
            # Footer rule
            stream.append(
                f"0.5 w 0.8 0.8 0.8 RG {self.MARGIN_LEFT:.1f} 45 m {self.MARGIN_RIGHT:.1f} 45 l S\n"
            )
            footer_left = _escape_pdf(
                f"DOSSIER: {dossier_id} | CONFIDENTIAL INVESTIGATION WORK PRODUCT"
            )
            footer_right = _escape_pdf(f"Page {idx} of {total_pages}")
            stream.append(
                f"BT /F3 7.5 Tf 0.35 0.35 0.35 rg {self.MARGIN_LEFT:.1f} 32 Td ({footer_left}) Tj ET\n"
            )
            stream.append(
                f"BT /F2 8 Tf 0.35 0.35 0.35 rg {self.MARGIN_RIGHT - 60.0:.1f} 32 Td ({footer_right}) Tj ET\n"
            )
            page.Contents = self.pdf.make_stream("".join(stream).encode("latin-1"))

        buf = io.BytesIO()
        self.pdf.save(buf, deterministic_id=True)
        return buf.getvalue()


class PdfDossierExporter:
    """Exports an InvestigationDossier to a multi-page PDF document."""

    def export(self, dossier: InvestigationDossier) -> bytes:
        """Render complete dossier into PDF bytes."""
        pdf = pikepdf.new()
        canvas = _PdfCanvas(pdf)

        # 1. Title & Case Header
        canvas.add_title(dossier.title)
        canvas.add_key_value("Case ID", dossier.case_id)
        canvas.add_key_value("Dossier ID", dossier.id)
        canvas.add_key_value("Version", str(dossier.version))
        canvas.add_key_value(
            "Status",
            dossier.status.value if hasattr(dossier.status, "value") else str(dossier.status),
        )
        canvas.add_key_value("Created By", dossier.created_by)
        canvas.add_key_value(
            "Generated At",
            dossier.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if dossier.created_at else "N/A",
        )
        if dossier.content_hash:
            canvas.add_key_value("Content Hash (SHA-256)", dossier.content_hash[:32] + "...")
        canvas.add_divider()

        # 2. Prominent Legal Disclaimer
        disclaimer_text = (
            "NOTICE: This dossier is a structured compilation of automated forensic indicators, deterministic "
            "consistency checks, and investigator reviews. It does NOT constitute an automated fraud determination, "
            "criminal accusation, or binding legal conclusion. All automated indicators require independent corroboration."
        )
        canvas.add_disclaimer_box(disclaimer_text)

        # 3. Executive Summary
        canvas.add_subheading("Executive Summary")
        canvas.add_paragraph(dossier.executive_summary)
        canvas.add_divider()

        # 4. Render All 12 Sections
        for section in sorted(dossier.sections, key=lambda s: s.order):
            canvas.add_section_heading(section.title)
            if section.content:
                canvas.add_paragraph(section.content)

            # Detail items if present
            if section.items:
                canvas.current_y -= 4.0
                for item in section.items[:25]:  # Limit item display to fit cleanly
                    if "file_name" in item:
                        # Document item
                        sha_snip = (item.get("sha256") or item.get("hash_sha256", ""))[:16]
                        canvas.add_bullet(
                            f"{item.get('file_name')} (SHA: {sha_snip}... | Pages: {item.get('page_count', 0)})"
                        )
                    elif "title" in item and "severity" in item:
                        # Finding item
                        canvas.add_bullet(f"[{item.get('severity')}] {item.get('title')}")
                    elif "relationship_type" in item:
                        # Relationship item
                        canvas.add_bullet(
                            f"{item.get('relationship_type')} ({item.get('status')}): {item.get('rationale', '')}"
                        )
                    elif "reviewer_id" in item:
                        # Review item
                        canvas.add_bullet(
                            f"{item.get('action')} by {item.get('reviewer_id')}: {item.get('rationale', '')}"
                        )
                    elif "question" in item:
                        # Unresolved question item
                        canvas.add_bullet(item.get("question", ""))
                    elif "limitation" in item:
                        # Limitation item
                        canvas.add_bullet(item.get("limitation", ""))
                    else:
                        summary_str = ", ".join(f"{k}: {v}" for k, v in list(item.items())[:3])
                        canvas.add_bullet(summary_str)

            canvas.current_y -= 6.0

        return canvas.finalize(dossier.id)
