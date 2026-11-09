"""PDF structural forensics adapter package."""

from document_intelligence.modules.forensics.adapters.pdf_structural.adapter import (
    PdfStructuralAnalyzer,
)
from document_intelligence.modules.forensics.adapters.pdf_structural.capabilities import (
    PdfCapability,
)

__all__ = ["PdfStructuralAnalyzer", "PdfCapability"]
