"""Base detector interface and detection context for cross-document relationship engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMention,
    ResolvedEntity,
)
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.domain.models.relationship import DetectedRelationship


@dataclass
class DetectionContext:
    """Execution context containing all documents, extracted fields, and resolved entities for a case."""

    case_id: str
    detection_run_id: str
    documents: list[Document]
    extracted_fields_by_doc: dict[str, list[ExtractedFieldValue]] = field(default_factory=dict)
    resolved_entities: list[ResolvedEntity] = field(default_factory=list)
    candidate_matches: list[EntityCandidateMatch] = field(default_factory=list)
    entity_mentions: list[EntityMention] = field(default_factory=list)
    raw_document_texts: dict[str, str] = field(default_factory=dict)
    synthetic_transactions: list[dict[str, Any]] = field(default_factory=list)


class BaseRelationshipDetector(ABC):
    """Abstract interface for a deterministic relationship detector."""

    @property
    @abstractmethod
    def detector_name(self) -> str:
        """Unique identifier name of this detector."""
        pass

    @property
    @abstractmethod
    def detector_version(self) -> str:
        """Semantic version of this detector."""
        pass

    @abstractmethod
    def detect(self, context: DetectionContext) -> list[DetectedRelationship]:
        """Detect deterministic relationships from the provided context."""
        pass
