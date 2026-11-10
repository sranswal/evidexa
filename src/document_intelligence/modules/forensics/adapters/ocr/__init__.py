"""OCR and Document Understanding engine adapters."""

from document_intelligence.modules.forensics.adapters.ocr.artifact_manager import (
    PP_OCRV4_LATIN_BASELINE,
    PP_OCRV5_DEVANAGARI,
    ApprovedModelArtifact,
    ModelArtifactCorruptError,
    ModelArtifactError,
    ModelArtifactNotFoundError,
    ModelArtifactSecurityError,
    OcrModelArtifactManager,
    VerifiedModelArtifact,
)
from document_intelligence.modules.forensics.adapters.ocr.devanagari_adapter import (
    DevanagariRapidOcrAdapter,
)
from document_intelligence.modules.forensics.adapters.ocr.hybrid_adapter import (
    HybridOcrAdapter,
)
from document_intelligence.modules.forensics.adapters.ocr.pdfium_adapter import (
    PdfiumOcrAdapter,
)
from document_intelligence.modules.forensics.adapters.ocr.rapidocr_adapter import (
    RapidOcrAdapter,
)

__all__ = [
    "ApprovedModelArtifact",
    "DevanagariRapidOcrAdapter",
    "HybridOcrAdapter",
    "ModelArtifactCorruptError",
    "ModelArtifactError",
    "ModelArtifactNotFoundError",
    "ModelArtifactSecurityError",
    "OcrModelArtifactManager",
    "PP_OCRV4_LATIN_BASELINE",
    "PP_OCRV5_DEVANAGARI",
    "PdfiumOcrAdapter",
    "RapidOcrAdapter",
    "VerifiedModelArtifact",
]
