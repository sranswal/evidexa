"""Unit tests for Evidence Graph domain contracts and sanitization."""

from __future__ import annotations

import uuid

from document_intelligence.domain.enums import GraphEdgePredicate, GraphNodeType
from document_intelligence.domain.models.graph import (
    GraphEdge,
    GraphNode,
    GraphPath,
    deterministic_edge_id,
    deterministic_node_id,
)
from document_intelligence.modules.graph.projector import sanitize_display_label


class TestGraphDomainContracts:
    """Validate domain model integrity and deterministic hashing."""

    def test_deterministic_node_id_is_stable_and_uuid(self) -> None:
        """Deterministic node ID must be a valid UUIDv5 and identical across identical inputs."""
        case_id = "test-case-uuid-1"
        source_id = "doc-123"

        id1 = deterministic_node_id(case_id, GraphNodeType.DOCUMENT, source_id)
        id2 = deterministic_node_id(case_id, GraphNodeType.DOCUMENT, source_id)

        assert id1 == id2
        assert len(id1) == 36
        assert id1.count("-") == 4
        # Validate parseable as UUID
        parsed = uuid.UUID(id1)
        assert parsed.version == 5

    def test_deterministic_edge_id_is_stable_and_uuid(self) -> None:
        """Deterministic edge ID must be a valid UUIDv5 and identical across identical inputs."""
        case_id = "test-case-uuid-1"
        source_node_id = "node-1"
        target_node_id = "node-2"
        predicate = GraphEdgePredicate.ISSUED

        id1 = deterministic_edge_id(case_id, source_node_id, predicate, target_node_id)
        id2 = deterministic_edge_id(case_id, source_node_id, predicate, target_node_id)

        assert id1 == id2
        assert len(id1) == 36
        parsed = uuid.UUID(id1)
        assert parsed.version == 5

    def test_graph_node_creation_and_attributes(self) -> None:
        """Verify GraphNode instantiation and safe attribute retention."""
        node = GraphNode(
            case_id="case-100",
            node_type=GraphNodeType.ORGANIZATION,
            source_entity_type="Organization",
            source_entity_id="org-555",
            label="Acme Global Inc.",
            display_attributes={"tax_id": "XX-1234567"},
            provenance={"document_id": "doc-1", "page_number": 1},
        )

        assert node.node_type == GraphNodeType.ORGANIZATION
        assert node.label == "Acme Global Inc."
        assert node.source_entity_id == "org-555"
        assert len(node.id) == 36

    def test_graph_edge_creation_and_preservation(self) -> None:
        """Verify GraphEdge instantiation with explicit status and evidence references."""
        edge = GraphEdge(
            case_id="case-100",
            source_node_id="node-a",
            target_node_id="node-b",
            predicate="INVOICED",
            status="CONFIRMED",
            status_determination_method="EVIDENTIARY_RULE",
            score=0.95,
            supporting_evidence_ids=["ev-1", "ev-2"],
            contradicting_evidence_ids=[],
            explanation="Single commercial invoice billing event",
        )

        assert edge.predicate == "INVOICED"
        assert edge.status == "CONFIRMED"
        assert edge.score == 0.95
        assert len(edge.supporting_evidence_ids) == 2

    def test_sanitize_display_label_masks_account_numbers(self) -> None:
        """Sanitization must mask sensitive account digits to prevent plaintext PII leakage."""
        masked_acc = sanitize_display_label("Account 98765432100", GraphNodeType.ACCOUNT)
        assert "98765432100" not in masked_acc
        assert "****2100" in masked_acc or "****" in masked_acc

        # General 8+ digit sequences masked
        raw_text = "Wire reference 1234567890 confirmed"
        sanitized = sanitize_display_label(raw_text, GraphNodeType.ORGANIZATION)
        assert "1234567890" not in sanitized
        assert "****7890" in sanitized

    def test_graph_path_model(self) -> None:
        """Verify GraphPath represents an ordered chain of nodes and edges."""
        n1 = GraphNode(
            case_id="c1",
            node_type=GraphNodeType.DOCUMENT,
            source_entity_type="Document",
            source_entity_id="d1",
            label="Doc 1",
        )
        n2 = GraphNode(
            case_id="c1",
            node_type=GraphNodeType.ORGANIZATION,
            source_entity_type="Organization",
            source_entity_id="o1",
            label="Org 1",
        )
        edge = GraphEdge(
            case_id="c1",
            source_node_id=n1.id,
            target_node_id=n2.id,
            predicate="ISSUED_BY",
            status="CONFIRMED",
        )

        path = GraphPath(nodes=[n1, n2], edges=[edge], length=1, is_confirmed_only=True)
        assert path.length == 1
        assert path.is_confirmed_only is True
        assert len(path.nodes) == 2
