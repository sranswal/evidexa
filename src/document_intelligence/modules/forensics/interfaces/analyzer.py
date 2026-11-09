"""Abstract contract defining the engine-independent ForensicAnalyzer protocol."""

from typing import Protocol, runtime_checkable

from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from document_intelligence.modules.forensics.schemas.analyzer_output import AnalyzerOutput


@runtime_checkable
class ForensicAnalyzer(Protocol):
    """Protocol defining the standard interface for all forensic engine adapters."""

    @property
    def analyzer_id(self) -> str:
        """Unique machine identifier for the analyzer (e.g. 'pdf-structural-analyzer')."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable display name for the analyzer."""
        ...

    @property
    def name(self) -> str:
        """Pipeline name for the analyzer."""
        ...

    @property
    def version(self) -> str:
        """Semantic version of the analyzer adapter."""
        ...

    @property
    def supported_media_types(self) -> set[str]:
        """Set of MIME media types this analyzer can process."""
        ...

    @property
    def supported_capabilities(self) -> list[str]:
        """List of specific capability identifiers supported by this analyzer."""
        ...

    def can_analyze(self, media_type: str) -> bool:
        """Return True if this analyzer supports the provided media type."""
        ...

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute forensic analysis on the target document and return normalized output.

        Must not modify the source document.
        Must not interact directly with database sessions or HTTP requests.
        """
        ...
