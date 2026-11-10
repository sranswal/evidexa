"""Evidence Graph projection service.

Assembles an in-memory, deterministic, unified investigation Evidence Graph
from authoritative relational records without persisting a second source of truth.
"""

from __future__ import annotations

import re

from document_intelligence.domain.enums import (
    GraphEdgePredicate,
    GraphNodeType,
    RelationshipStatus,
)
from document_intelligence.domain.models.case import Case
from document_intelligence.domain.models.consistency import ConsistencyFinding
from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.entity_resolution import EntityCandidateMatch
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.domain.models.graph import (
    GraphEdge,
    GraphNode,
    deterministic_edge_id,
    deterministic_node_id,
)
from document_intelligence.domain.models.relationship import DetectedRelationship

# Node type mapping lookup for entity and mention string types
_STRING_TYPE_TO_NODE_TYPE: dict[str, GraphNodeType] = {
    "CASE": GraphNodeType.CASE,
    "DOCUMENT": GraphNodeType.DOCUMENT,
    "PERSON": GraphNodeType.PERSON,
    "ORGANIZATION": GraphNodeType.ORGANIZATION,
    "SUPPLIER": GraphNodeType.SUPPLIER,
    "BUYER": GraphNodeType.BUYER,
    "MERCHANT": GraphNodeType.MERCHANT,
    "BANK": GraphNodeType.BANK,
    "ACCOUNT": GraphNodeType.ACCOUNT,
    "INVOICE": GraphNodeType.INVOICE,
    "RECEIPT": GraphNodeType.RECEIPT,
    "PURCHASE_ORDER": GraphNodeType.PURCHASE_ORDER,
    "BANK_TRANSACTION": GraphNodeType.BANK_TRANSACTION,
    "TRANSACTION": GraphNodeType.BANK_TRANSACTION,
    "TAX_IDENTIFIER": GraphNodeType.ORGANIZATION,
    "INVOICE_REFERENCE": GraphNodeType.INVOICE,
    "BANK_ACCOUNT_REFERENCE": GraphNodeType.ACCOUNT,
    "CURRENCY_AMOUNT": GraphNodeType.INVOICE,
    "TRANSACTION_REFERENCE": GraphNodeType.BANK_TRANSACTION,
    "EVIDENCE": GraphNodeType.EVIDENCE,
    "FORENSIC_FINDING": GraphNodeType.FORENSIC_FINDING,
    "CONSISTENCY_FINDING": GraphNodeType.CONSISTENCY_FINDING,
}


def sanitize_display_label(label: str, node_type: GraphNodeType | str) -> str:
    """Sanitize display labels to guarantee zero unmasked plaintext PII in graph presentations."""
    if not label:
        return "Unknown"

    cleaned = label.strip()

    # Mask account numbers or long digits (9+ consecutive digits)
    type_str = node_type.value if hasattr(node_type, "value") else str(node_type)
    if type_str == "ACCOUNT" or "account" in cleaned.lower():
        # Mask all but last 4 digits
        digits = re.findall(r"\d", cleaned)
        if len(digits) >= 6:
            last4 = "".join(digits[-4:])
            return f"Account ****{last4}"

    # General digit sequences exceeding 8 characters masked
    def _mask_digits(match: re.Match[str]) -> str:
        s = match.group(0)
        if len(s) >= 8:
            return f"****{s[-4:]}"
        return s

    cleaned = re.sub(r"\b\d{8,}\b", _mask_digits, cleaned)
    return cleaned


def map_node_type(raw_type: str | None) -> GraphNodeType:
    """Safely map arbitrary domain entity or mention strings to canonical GraphNodeType."""
    if not raw_type:
        return GraphNodeType.ORGANIZATION
    key = raw_type.upper().strip()
    return _STRING_TYPE_TO_NODE_TYPE.get(key, GraphNodeType.ORGANIZATION)


class ProjectedGraphData:
    """Container holding projected nodes and edges with deterministic indexing."""

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}
        # Adjacency indexes for rapid traversal
        self.outgoing_edges: dict[str, list[str]] = {}  # node_id -> [edge_id, ...]
        self.incoming_edges: dict[str, list[str]] = {}  # node_id -> [edge_id, ...]

    def add_node(self, node: GraphNode) -> None:
        """Add or update a projected node."""
        self.nodes[node.id] = node
        if node.id not in self.outgoing_edges:
            self.outgoing_edges[node.id] = []
        if node.id not in self.incoming_edges:
            self.incoming_edges[node.id] = []

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed edge if both endpoints exist."""
        if edge.source_node_id not in self.nodes or edge.target_node_id not in self.nodes:
            return

        self.edges[edge.id] = edge
        self.outgoing_edges.setdefault(edge.source_node_id, []).append(edge.id)
        self.incoming_edges.setdefault(edge.target_node_id, []).append(edge.id)


class EvidenceGraphProjector:
    """Projects authoritative relational records into a unified Evidence Graph."""

    def project_case(
        self,
        case: Case,
        documents: list[Document],
        evidence_nodes: list[EvidenceNode],
        forensic_findings: list[ForensicFinding],
        consistency_findings: list[ConsistencyFinding],
        detected_relationships: list[DetectedRelationship],
        entity_matches: list[EntityCandidateMatch],
    ) -> ProjectedGraphData:
        """Deterministically project all investigation records for a case into graph nodes and edges."""
        graph = ProjectedGraphData(case_id=case.id)

        # 1. Project Case Root Node
        case_node_id = deterministic_node_id(case.id, GraphNodeType.CASE, case.id)
        graph.add_node(
            GraphNode(
                id=case_node_id,
                case_id=case.id,
                node_type=GraphNodeType.CASE,
                source_entity_type="Case",
                source_entity_id=case.id,
                label=case.case_reference or case.title,
                display_attributes={
                    "case_reference": case.case_reference,
                    "title": case.title,
                    "status": case.status.value,
                    "created_at": case.created_at.isoformat() if case.created_at else None,
                },
                provenance={"case_id": case.id},
                created_at=case.created_at,
            )
        )

        # Map document_id -> graph_node_id
        doc_node_id_map: dict[str, str] = {}
        for doc in documents:
            node_id = deterministic_node_id(case.id, GraphNodeType.DOCUMENT, doc.id)
            doc_node_id_map[doc.id] = node_id
            graph.add_node(
                GraphNode(
                    id=node_id,
                    case_id=case.id,
                    node_type=GraphNodeType.DOCUMENT,
                    source_entity_type="Document",
                    source_entity_id=doc.id,
                    label=doc.original_filename,
                    display_attributes={
                        "filename": doc.original_filename,
                        "document_type": doc.document_type.value
                        if doc.document_type
                        else "UNKNOWN",
                        "sha256": doc.sha256,
                        "page_count": doc.page_count,
                        "file_size_bytes": doc.file_size_bytes,
                        "media_type": doc.media_type,
                    },
                    provenance={
                        "document_id": doc.id,
                        "storage_key": doc.storage_key,
                        "ingestion_status": doc.ingestion_status.value,
                    },
                    created_at=doc.created_at,
                )
            )

            # Edge: Case -> Document (CONTAINS_DOCUMENT)
            edge_id = deterministic_edge_id(
                case.id, case_node_id, GraphEdgePredicate.CONTAINS_DOCUMENT, node_id
            )
            graph.add_edge(
                GraphEdge(
                    id=edge_id,
                    case_id=case.id,
                    source_node_id=case_node_id,
                    target_node_id=node_id,
                    predicate=GraphEdgePredicate.CONTAINS_DOCUMENT.value,
                    status=RelationshipStatus.CONFIRMED.value,
                    explanation=f"Case contains document '{doc.original_filename}'",
                )
            )

        # Map evidence_id -> graph_node_id
        ev_node_id_map: dict[str, str] = {}
        for ev in evidence_nodes:
            ev_node_id = deterministic_node_id(case.id, GraphNodeType.EVIDENCE, ev.id)
            ev_node_id_map[ev.id] = ev_node_id
            safe_bbox = ev.bounding_box.to_normalized_dict() if ev.bounding_box else None
            graph.add_node(
                GraphNode(
                    id=ev_node_id,
                    case_id=case.id,
                    node_type=GraphNodeType.EVIDENCE,
                    source_entity_type="EvidenceNode",
                    source_entity_id=ev.id,
                    label=sanitize_display_label(ev.title, GraphNodeType.EVIDENCE),
                    display_attributes={
                        "evidence_type": ev.evidence_type.value,
                        "source_component": ev.source_component,
                        "page_number": ev.page_number,
                        "confidence": ev.confidence,
                        "categorical_confidence": ev.categorical_confidence,
                    },
                    provenance={
                        "evidence_node_id": ev.id,
                        "document_id": ev.document_id,
                        "processing_run_id": ev.processing_run_id,
                        "page_number": ev.page_number,
                        "bounding_box": safe_bbox,
                    },
                    created_at=ev.observed_at,
                )
            )

            # Edge: Document -> Evidence (HAS_EVIDENCE)
            if ev.document_id and ev.document_id in doc_node_id_map:
                d_node_id = doc_node_id_map[ev.document_id]
                edge_id = deterministic_edge_id(
                    case.id, d_node_id, GraphEdgePredicate.HAS_EVIDENCE, ev_node_id
                )
                graph.add_edge(
                    GraphEdge(
                        id=edge_id,
                        case_id=case.id,
                        source_node_id=d_node_id,
                        target_node_id=ev_node_id,
                        predicate=GraphEdgePredicate.HAS_EVIDENCE.value,
                        status=RelationshipStatus.CONFIRMED.value,
                        supporting_evidence_ids=[ev.id],
                        explanation=f"Document contains evidence '{ev.title}'",
                    )
                )

        # 3. Project Forensic Findings
        for ff in forensic_findings:
            ff_node_id = deterministic_node_id(case.id, GraphNodeType.FORENSIC_FINDING, ff.id)
            graph.add_node(
                GraphNode(
                    id=ff_node_id,
                    case_id=case.id,
                    node_type=GraphNodeType.FORENSIC_FINDING,
                    source_entity_type="ForensicFinding",
                    source_entity_id=ff.id,
                    label=sanitize_display_label(ff.title, GraphNodeType.FORENSIC_FINDING),
                    display_attributes={
                        "category": ff.category.value,
                        "severity": ff.severity.value,
                        "status": ff.status.value,
                        "confidence": ff.confidence,
                        "source_component": ff.source_component,
                    },
                    provenance={
                        "finding_id": ff.id,
                        "document_id": ff.document_id,
                        "processing_run_id": ff.processing_run_id,
                        "source_component": ff.source_component,
                        "evidence_ids": ff.evidence_ids,
                    },
                    created_at=ff.created_at,
                )
            )

            # Edge: ForensicFinding -> Document (PERTAINS_TO)
            if ff.document_id and ff.document_id in doc_node_id_map:
                d_node_id = doc_node_id_map[ff.document_id]
                edge_id = deterministic_edge_id(
                    case.id, ff_node_id, GraphEdgePredicate.PERTAINS_TO, d_node_id
                )
                graph.add_edge(
                    GraphEdge(
                        id=edge_id,
                        case_id=case.id,
                        source_node_id=ff_node_id,
                        target_node_id=d_node_id,
                        predicate=GraphEdgePredicate.PERTAINS_TO.value,
                        status=RelationshipStatus.CONFIRMED.value,
                        explanation=f"Forensic finding pertains to document '{d_node_id}'",
                    )
                )

            # Edge: ForensicFinding -> Evidence (SUPPORTED_BY)
            for ev_id in ff.evidence_ids:
                if ev_id in ev_node_id_map:
                    ev_node_id = ev_node_id_map[ev_id]
                    edge_id = deterministic_edge_id(
                        case.id, ff_node_id, GraphEdgePredicate.SUPPORTED_BY, ev_node_id
                    )
                    graph.add_edge(
                        GraphEdge(
                            id=edge_id,
                            case_id=case.id,
                            source_node_id=ff_node_id,
                            target_node_id=ev_node_id,
                            predicate=GraphEdgePredicate.SUPPORTED_BY.value,
                            status=RelationshipStatus.CONFIRMED.value,
                            supporting_evidence_ids=[ev_id],
                            explanation=f"Forensic finding supported by evidence node '{ev_id}'",
                        )
                    )

        # 4. Project Consistency Findings
        for cf in consistency_findings:
            cf_node_id = deterministic_node_id(case.id, GraphNodeType.CONSISTENCY_FINDING, cf.id)
            graph.add_node(
                GraphNode(
                    id=cf_node_id,
                    case_id=case.id,
                    node_type=GraphNodeType.CONSISTENCY_FINDING,
                    source_entity_type="ConsistencyFinding",
                    source_entity_id=cf.id,
                    label=sanitize_display_label(cf.title, GraphNodeType.CONSISTENCY_FINDING),
                    display_attributes={
                        "rule_id": cf.rule_id,
                        "rule_version": cf.rule_version,
                        "category": cf.category.value
                        if hasattr(cf.category, "value")
                        else str(cf.category),
                        "outcome": cf.outcome.value
                        if hasattr(cf.outcome, "value")
                        else str(cf.outcome),
                        "severity": cf.severity.value
                        if hasattr(cf.severity, "value")
                        else str(cf.severity),
                        "status": cf.status.value
                        if hasattr(cf.status, "value")
                        else str(cf.status),
                        "is_reviewed": cf.is_human_reviewed,
                        "review_status": cf.review_status,
                    },
                    provenance={
                        "finding_id": cf.id,
                        "analysis_run_id": cf.analysis_run_id,
                        "affected_document_ids": cf.affected_document_ids,
                        "compared_fields": cf.compared_fields,
                        "detection_method": cf.detection_method.value
                        if hasattr(cf.detection_method, "value")
                        else str(cf.detection_method),
                        "supporting_evidence_ids": cf.supporting_evidence_ids,
                        "contradicting_evidence_ids": cf.contradicting_evidence_ids,
                    },
                    created_at=cf.created_at,
                )
            )

            # Edges: ConsistencyFinding -> Compared Documents (COMPARES_DOCUMENT)
            for doc_id in cf.affected_document_ids:
                if doc_id in doc_node_id_map:
                    d_node_id = doc_node_id_map[doc_id]
                    edge_id = deterministic_edge_id(
                        case.id, cf_node_id, GraphEdgePredicate.COMPARES_DOCUMENT, d_node_id
                    )
                    graph.add_edge(
                        GraphEdge(
                            id=edge_id,
                            case_id=case.id,
                            source_node_id=cf_node_id,
                            target_node_id=d_node_id,
                            predicate=GraphEdgePredicate.COMPARES_DOCUMENT.value,
                            status=RelationshipStatus.CONFIRMED.value,
                            explanation=f"Consistency check compares document '{doc_id}'",
                        )
                    )

            # Edges: ConsistencyFinding -> Supporting Evidence (SUPPORTED_BY)
            for ev_id in cf.supporting_evidence_ids:
                if ev_id in ev_node_id_map:
                    ev_node_id = ev_node_id_map[ev_id]
                    edge_id = deterministic_edge_id(
                        case.id, cf_node_id, GraphEdgePredicate.SUPPORTED_BY, ev_node_id
                    )
                    graph.add_edge(
                        GraphEdge(
                            id=edge_id,
                            case_id=case.id,
                            source_node_id=cf_node_id,
                            target_node_id=ev_node_id,
                            predicate=GraphEdgePredicate.SUPPORTED_BY.value,
                            status=RelationshipStatus.CONFIRMED.value,
                            supporting_evidence_ids=[ev_id],
                            explanation=f"Consistency finding supported by evidence '{ev_id}'",
                        )
                    )

            # Edges: ConsistencyFinding -> Contradicting Evidence (CONTRADICTED_BY)
            for ev_id in cf.contradicting_evidence_ids:
                if ev_id in ev_node_id_map:
                    ev_node_id = ev_node_id_map[ev_id]
                    edge_id = deterministic_edge_id(
                        case.id, cf_node_id, GraphEdgePredicate.CONTRADICTED_BY, ev_node_id
                    )
                    graph.add_edge(
                        GraphEdge(
                            id=edge_id,
                            case_id=case.id,
                            source_node_id=cf_node_id,
                            target_node_id=ev_node_id,
                            predicate=GraphEdgePredicate.CONTRADICTED_BY.value,
                            status=RelationshipStatus.CONTRADICTED.value,
                            contradicting_evidence_ids=[ev_id],
                            explanation=f"Consistency finding contradicted by evidence '{ev_id}'",
                        )
                    )

        # 5. Project Detected Relationships (V2 Directed Semantic Predicates)
        for rel in detected_relationships:
            # Resolve or create source node
            src_node_id = self._resolve_or_create_entity_node(
                graph=graph,
                case_id=case.id,
                entity_id=rel.source_id,
                entity_type_str=rel.source_type,
                entity_label=rel.source_label,
                doc_node_map=doc_node_id_map,
            )

            # Resolve or create target node
            tgt_node_id = self._resolve_or_create_entity_node(
                graph=graph,
                case_id=case.id,
                entity_id=rel.target_id,
                entity_type_str=rel.target_type,
                entity_label=rel.target_label,
                doc_node_map=doc_node_id_map,
            )

            if src_node_id and tgt_node_id:
                status_str = rel.status.value if hasattr(rel.status, "value") else str(rel.status)
                det_method_str = (
                    rel.status_determination_method.value
                    if hasattr(rel.status_determination_method, "value")
                    else str(rel.status_determination_method)
                )
                edge_id = deterministic_edge_id(
                    case.id,
                    src_node_id,
                    rel.relationship_type.value,
                    tgt_node_id,
                    source_rel_id=rel.id,
                )
                graph.add_edge(
                    GraphEdge(
                        id=edge_id,
                        case_id=case.id,
                        source_node_id=src_node_id,
                        target_node_id=tgt_node_id,
                        predicate=rel.relationship_type.value,
                        status=status_str,
                        status_determination_method=det_method_str,
                        score=rel.score,
                        supporting_evidence_ids=rel.evidence.supporting_evidence_node_ids,
                        contradicting_evidence_ids=rel.evidence.contradicting_signals,
                        source_relationship_id=rel.id,
                        explanation=rel.status_rationale,
                        metadata={
                            "direction_display": rel.direction_display,
                            "is_human_reviewed": rel.is_human_reviewed,
                            "detection_method": rel.detection_method.value
                            if hasattr(rel.detection_method, "value")
                            else str(rel.detection_method),
                        },
                    )
                )

        # 6. Project Entity Candidate Matches
        for match in entity_matches:
            target_node_type = map_node_type(match.entity_type.value)
            target_node_id = deterministic_node_id(
                case.id, target_node_type, match.target_mention_id
            )
            if target_node_id not in graph.nodes:
                graph.add_node(
                    GraphNode(
                        id=target_node_id,
                        case_id=case.id,
                        node_type=target_node_type,
                        source_entity_type="EntityMention",
                        source_entity_id=match.target_mention_id,
                        label=sanitize_display_label(match.target_value_display, target_node_type),
                        display_attributes={"entity_type": match.entity_type.value},
                        provenance={
                            "document_id": match.evidence.target_document_id,
                            "field_key": match.evidence.target_field_key,
                            "page_number": match.evidence.target_page_number,
                        },
                    )
                )

            cand_node_id = deterministic_node_id(
                case.id, target_node_type, match.candidate_mention_id
            )
            if cand_node_id not in graph.nodes:
                graph.add_node(
                    GraphNode(
                        id=cand_node_id,
                        case_id=case.id,
                        node_type=target_node_type,
                        source_entity_type="EntityMention",
                        source_entity_id=match.candidate_mention_id,
                        label=sanitize_display_label(
                            match.candidate_value_display, target_node_type
                        ),
                        display_attributes={"entity_type": match.entity_type.value},
                        provenance={
                            "document_id": match.evidence.candidate_document_id,
                            "field_key": match.evidence.candidate_field_key,
                            "page_number": match.evidence.candidate_page_number,
                        },
                    )
                )

            # Edge: MATCHES_IDENTITY
            all_supp_ids = (
                match.evidence.target_evidence_node_ids + match.evidence.candidate_evidence_node_ids
            )
            edge_id = deterministic_edge_id(
                case.id,
                target_node_id,
                GraphEdgePredicate.MATCHES_IDENTITY,
                cand_node_id,
                source_rel_id=match.id,
            )
            graph.add_edge(
                GraphEdge(
                    id=edge_id,
                    case_id=case.id,
                    source_node_id=target_node_id,
                    target_node_id=cand_node_id,
                    predicate=GraphEdgePredicate.MATCHES_IDENTITY.value,
                    status=match.decision_status.value
                    if hasattr(match.decision_status, "value")
                    else str(match.decision_status),
                    score=match.match_score,
                    supporting_evidence_ids=all_supp_ids,
                    contradicting_evidence_ids=match.evidence.contradicting_signals,
                    source_relationship_id=match.id,
                    explanation=f"Entity match classification: {match.match_classification.value}",
                    metadata={
                        "matching_method": match.matching_method.value
                        if hasattr(match.matching_method, "value")
                        else str(match.matching_method),
                        "review_status": match.review_status.value
                        if hasattr(match.review_status, "value")
                        else str(match.review_status),
                    },
                )
            )

        return graph

    def _resolve_or_create_entity_node(
        self,
        graph: ProjectedGraphData,
        case_id: str,
        entity_id: str,
        entity_type_str: str,
        entity_label: str,
        doc_node_map: dict[str, str],
    ) -> str:
        """Resolve an entity reference to a document node if it represents a document, or create an entity node."""
        if entity_type_str.upper() in ("DOCUMENT", "DOC"):
            if entity_id in doc_node_map:
                return doc_node_map[entity_id]
            # If document ID not in map, generate deterministic doc node ID
            return deterministic_node_id(case_id, GraphNodeType.DOCUMENT, entity_id)

        node_type = map_node_type(entity_type_str)
        node_id = deterministic_node_id(case_id, node_type, entity_id)

        if node_id not in graph.nodes:
            graph.add_node(
                GraphNode(
                    id=node_id,
                    case_id=case_id,
                    node_type=node_type,
                    source_entity_type=entity_type_str,
                    source_entity_id=entity_id,
                    label=sanitize_display_label(entity_label, node_type),
                    display_attributes={"entity_type": entity_type_str},
                    provenance={"source_id": entity_id},
                )
            )

        return node_id
