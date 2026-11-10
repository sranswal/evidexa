"""Execution context for deterministic cross-document consistency rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.entity_resolution import ResolvedEntity
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.domain.models.relationship import DetectedRelationship


@dataclass
class ConsistencyContext:
    """Case context containing extracted documents, fields, evidence, and entity signals."""

    case_id: str
    analysis_run_id: str
    documents: list[Document]
    extracted_fields_by_doc: dict[str, list[ExtractedFieldValue]] = field(default_factory=dict)
    evidence_nodes_by_doc: dict[str, list[EvidenceNode]] = field(default_factory=dict)
    resolved_entities: list[ResolvedEntity] = field(default_factory=list)
    detected_relationships: list[DetectedRelationship] = field(default_factory=list)
    raw_document_texts: dict[str, str] = field(default_factory=dict)
    synthetic_transactions: list[dict[str, Any]] = field(default_factory=list)
    monetary_tolerance: Decimal = Decimal("0.00")
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._doc_map: dict[str, Document] = {d.id: d for d in self.documents}
        self._fields_by_doc_map: dict[str, dict[str, ExtractedFieldValue]] = {}
        for doc_id, fields in self.extracted_fields_by_doc.items():
            self._fields_by_doc_map[doc_id] = {f.field_key: f for f in fields}

    def get_document(self, document_id: str) -> Document | None:
        """Lookup document by ID."""
        return self._doc_map.get(document_id)

    def get_field(self, document_id: str, field_key: str) -> ExtractedFieldValue | None:
        """Lookup an extracted field value by document ID and field key."""
        doc_fields = self._fields_by_doc_map.get(document_id)
        if not doc_fields:
            return None
        return doc_fields.get(field_key)

    def get_field_dict(self, document_id: str) -> dict[str, ExtractedFieldValue]:
        """Get all extracted fields for a document keyed by field_key."""
        return self._fields_by_doc_map.get(document_id, {})

    def get_evidence_for_field(self, document_id: str, field_key: str) -> list[EvidenceNode]:
        """Find atomic evidence nodes associated with this field key."""
        nodes = self.evidence_nodes_by_doc.get(document_id, [])
        return [
            n
            for n in nodes
            if n.metadata.get("field_key") == field_key
            or (n.raw_value and field_key in n.description.lower())
        ]
