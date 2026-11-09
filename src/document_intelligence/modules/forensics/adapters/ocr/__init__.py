"""OCR and Document Understanding engine adapters."""

from document_intelligence.modules.forensics.adapters.ocr.hybrid_adapter import HybridOcrAdapter
from document_intelligence.modules.forensics.adapters.ocr.pdfium_adapter import PdfiumOcrAdapter
from document_intelligence.modules.forensics.adapters.ocr.rapidocr_adapter import RapidOcrAdapter

__all__ = [
    "HybridOcrAdapter",
    "PdfiumOcrAdapter",
    "RapidOcrAdapter",
]
