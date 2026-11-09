"""Schemas for forensic analyzers."""

from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from document_intelligence.modules.forensics.schemas.analyzer_output import (
    AnalyzerCapabilityResult,
    AnalyzerObservation,
    AnalyzerOutput,
)

__all__ = [
    "AnalyzerInput",
    "AnalyzerObservation",
    "AnalyzerCapabilityResult",
    "AnalyzerOutput",
]
