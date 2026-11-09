"""Forensic application services."""

from document_intelligence.modules.forensics.application.processing_service import (
    ForensicProcessingService,
)
from document_intelligence.modules.forensics.application.result_normalizer import (
    ForensicResultNormalizer,
)

__all__ = ["ForensicProcessingService", "ForensicResultNormalizer"]
