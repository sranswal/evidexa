"""Verified capabilities matrix and constants for PDF structural forensics."""

from enum import StrEnum


class PdfCapability(StrEnum):
    """Verified structural analysis capabilities provided by pdf-forensics-kit."""

    STRUCTURE = "pdf.structure"
    REVISIONS = "pdf.revisions"
    SIGNATURES = "pdf.signatures"
    PDFSIG = "pdf.pdfsig"
    METADATA = "pdf.metadata"
    CONTENT = "pdf.content"
    ACTIVE_CONTENT = "pdf.active_content"
    FINGERPRINT = "pdf.fingerprint"
    TIMELINE = "pdf.timeline"


CAPABILITY_DESCRIPTIONS: dict[PdfCapability, str] = {
    PdfCapability.STRUCTURE: "Classic/stream cross-reference tables, EOF marker counts, and trailer dictionary inspection.",
    PdfCapability.REVISIONS: "Incremental update tracking, revision counting, modified object detection, and revision text diff.",
    PdfCapability.SIGNATURES: "Cryptographic signature dictionary detection and CMS integrity validation.",
    PdfCapability.PDFSIG: "External pdfsig tool cross-checking (optional).",
    PdfCapability.METADATA: "Information dictionary vs XMP stream comparison, author/producer provenance, and timestamp drift.",
    PdfCapability.CONTENT: "Invisible text detection, rendering modes, and OCR text layer classification.",
    PdfCapability.ACTIVE_CONTENT: "JavaScript actions (/JS, /JavaScript), launch triggers (/Launch), and embedded file payloads (/EmbeddedFiles).",
    PdfCapability.FINGERPRINT: "Known generator signature matching (e.g. Acrobat, iText, Ghostscript, pdfTeX).",
    PdfCapability.TIMELINE: "Chronological consistency verification across creation, modification, and signing events.",
}
