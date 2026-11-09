"""Registry for discovering and managing ForensicAnalyzer adapters."""

from document_intelligence.core.exceptions import ValidationException
from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer


class AnalyzerRegistry:
    """Thread-safe registry for managing registered forensic analyzers."""

    def __init__(self) -> None:
        self._analyzers: dict[str, ForensicAnalyzer] = {}

    def register(self, analyzer: ForensicAnalyzer) -> None:
        """Register a forensic analyzer instance. Raises ValidationException on duplicate ID."""
        aid = analyzer.analyzer_id
        if aid in self._analyzers:
            raise ValidationException(
                f"Analyzer with ID '{aid}' is already registered.",
                details={"analyzer_id": aid},
            )
        self._analyzers[aid] = analyzer

    def get(self, analyzer_id: str) -> ForensicAnalyzer | None:
        """Retrieve analyzer by ID."""
        return self._analyzers.get(analyzer_id)

    def list_analyzers(self) -> list[ForensicAnalyzer]:
        """Return list of all registered analyzers."""
        return list(self._analyzers.values())

    def get_for_media_type(self, media_type: str) -> list[ForensicAnalyzer]:
        """Return all analyzers capable of handling the specified media type."""
        return [a for a in self._analyzers.values() if a.can_analyze(media_type)]


# Global default registry instance
default_registry = AnalyzerRegistry()
