"""Forensic interfaces."""

from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer
from document_intelligence.modules.forensics.interfaces.registry import (
    AnalyzerRegistry,
    default_registry,
)

__all__ = ["ForensicAnalyzer", "AnalyzerRegistry", "default_registry"]
