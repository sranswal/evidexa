"""Unit tests for Evidence Graph projection service."""

from __future__ import annotations

from document_intelligence.domain.enums import (
    CaseStatus,
    ConsistencyDetectionMethod,
    ConsistencyOutcome,
    DocumentType,
    EntityMatchClassification,
    EntityMatchingMethod,
    EvidenceType,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    GraphEdgePredicate,
    GraphNodeType,
    IngestionStatus,
    MatchDecisionStatus,
    RelationshipDetectionMethod,
    RelationshipStatus,
    RelationshipType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.case import Case
from document_intelligence.domain.models.consistency import (
    ConsistencyComparison,
    ConsistencyEvidence,
    ConsistencyFinding,
)
from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMatchEvidence,
)
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.domain.models.graph import deterministic_node_id
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipEvidence,
)
from document_intelligence.modules.graph.projector import EvidenceGraphProjector


def _sample_case() -> Case:
    return Case(
        id="case-uuid-001",
        title="Project Falcon Investigation",
        description="Cross-document procurement inquiry",
        case_reference="CASE-2026-FALCON",
        status=CaseStatus.ACTIVE,
    )


def _sample_documents() -> list[Document]:
    return [
        Document(
            id="doc-inv-1",
            case_id="case-uuid-001",
            original_filename="invoice_101.pdf",
            media_type="application/pdf",
            file_extension=".pdf",
            file_size_bytes=45000,
            sha256="1" * 64,
            storage_key="cases/case-uuid-001/invoice_101.pdf",
            document_type=DocumentType.INVOICE,
            ingestion_status=IngestionStatus.STORED,
        ),
        Document(
            id="doc-po-1",
            case_id="case-uuid-001",
            original_filename="purchase_order_50.pdf",
            media_type="application/pdf",
            file_extension=".pdf",
            file_size_bytes=52000,
            sha256="2" * 64,
            storage_key="cases/case-uuid-001/purchase_order_50.pdf",
            document_type=DocumentType.PURCHASE_ORDER,
            ingestion_status=IngestionStatus.STORED,
        ),
    ]


def _sample_evidence() -> list[EvidenceNode]:
    return [
        EvidenceNode(
            id="ev-token-1",
            case_id="case-uuid-001",
            document_id="doc-inv-1",
            processing_run_id="run-1",
            evidence_type=EvidenceType.OCR_TEXT,
            title="Invoice Header Reference",
            description="Extracted token INV-101",
            source_component="hybrid_ocr",
            source_version="1.0.0",
            page_number=1,
            bounding_box=BoundingBox(x=0.1, y=0.1, width=0.3, height=0.05),
            confidence=0.98,
        ),
        EvidenceNode(
            id="ev-ela-1",
            case_id="case-uuid-001",
            document_id="doc-inv-1",
            processing_run_id="run-1",
            evidence_type=EvidenceType.VISUAL_REGION,
            title="ELA Compression Discrepancy",
            description="High error rate in total amount box",
            source_component="ela_analyzer",
            source_version="1.0.0",
            page_number=1,
            confidence=0.85,
        ),
    ]


def _sample_forensic_findings() -> list[ForensicFinding]:
    return [
        ForensicFinding(
            id="ff-1",
            case_id="case-uuid-001",
            document_id="doc-inv-1",
            processing_run_id="run-1",
            category=FindingCategory.VISUAL_ANOMALY,
            title="Suspected Digit Alteration",
            description="ELA variance detected on amount block",
            severity=FindingSeverity.HIGH,
            status=FindingStatus.DETECTED,
            evidence_ids=["ev-ela-1"],
            source_component="ela_analyzer",
        )
    ]


def _sample_consistency_findings() -> list[ConsistencyFinding]:
    return [
        ConsistencyFinding(
            id="cf-1",
            case_id="case-uuid-001",
            analysis_run_id="run-c-1",
            rule_id="CONSISTENCY-B03-FINANCIALS",
            category=FindingCategory.CROSS_DOCUMENT_MISMATCH,
            title="Invoice Total Exceeds Purchase Order",
            explanation="Invoice total 12000.00 USD exceeds authorized PO total 10000.00 USD",
            severity=FindingSeverity.HIGH,
            outcome=ConsistencyOutcome.INCONSISTENT,
            affected_document_ids=["doc-inv-1", "doc-po-1"],
            compared_fields=["total_amount"],
            supporting_evidence_ids=["ev-token-1"],
            contradicting_evidence_ids=["ev-ela-1"],
            comparisons=[
                ConsistencyComparison(
                    field_key="total_amount",
                    source_doc_id="doc-po-1",
                    source_value="10000.00",
                    target_doc_id="doc-inv-1",
                    target_value="12000.00",
                    comparison_type="DECIMAL_MONETARY",
                    outcome=ConsistencyOutcome.INCONSISTENT,
                    difference="2000.00 USD overrun",
                    explanation="Authorized amount exceeded",
                )
            ],
            evidence=ConsistencyEvidence(
                supporting_evidence_node_ids=["ev-token-1"],
                contradicting_evidence_node_ids=["ev-ela-1"],
                detection_method=ConsistencyDetectionMethod.MONETARY_RECONCILIATION_CHECK,
            ),
        )
    ]


def _sample_relationships() -> list[DetectedRelationship]:
    return [
        DetectedRelationship(
            id="rel-1",
            case_id="case-uuid-001",
            detection_run_id="run-r-1",
            relationship_type=RelationshipType.REFERENCES_PURCHASE_ORDER,
            source_id="doc-inv-1",
            source_type="DOCUMENT",
            source_label="invoice_101.pdf",
            target_id="doc-po-1",
            target_type="DOCUMENT",
            target_label="purchase_order_50.pdf",
            direction_display="invoice_101.pdf --REFERENCES_PURCHASE_ORDER--> purchase_order_50.pdf",
            status=RelationshipStatus.CONFIRMED,
            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
            score=0.99,
            score_semantics="exact_field_citation",
            detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
            status_rationale="Invoice field po_number explicitly cites PO-50",
            evidence=RelationshipEvidence(
                relationship_type=RelationshipType.REFERENCES_PURCHASE_ORDER,
                source_id="doc-inv-1",
                target_id="doc-po-1",
                source_case_id="case-uuid-001",
                score=0.99,
                score_semantics="exact_field_citation",
                status=RelationshipStatus.CONFIRMED,
                status_rationale="Explicit citation match",
                supporting_evidence_node_ids=["ev-token-1"],
            ),
        ),
        DetectedRelationship(
            id="rel-2",
            case_id="case-uuid-001",
            detection_run_id="run-r-1",
            relationship_type=RelationshipType.INVOICED,
            source_id="org-vendor-a",
            source_type="ORGANIZATION",
            source_label="Apex Supplies LLC",
            target_id="org-buyer-b",
            target_type="ORGANIZATION",
            target_label="Global Enterprises Corp",
            direction_display="Apex Supplies LLC --INVOICED--> Global Enterprises Corp",
            status=RelationshipStatus.CANDIDATE,
            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
            score=0.85,
            score_semantics="commercial_billing_event",
            detection_method=RelationshipDetectionMethod.INVOICE_BILLING_EVENT_RULE,
            status_rationale="Commercial invoice billing event between supplier and buyer",
            evidence=RelationshipEvidence(
                relationship_type=RelationshipType.INVOICED,
                source_id="org-vendor-a",
                target_id="org-buyer-b",
                source_case_id="case-uuid-001",
                score=0.85,
                score_semantics="commercial_billing_event",
                status=RelationshipStatus.CANDIDATE,
                status_rationale="Commercial invoice billing event",
            ),
        ),
    ]


def _sample_entity_matches() -> list[EntityCandidateMatch]:
    return [
        EntityCandidateMatch(
            id="match-1",
            case_id="case-uuid-001",
            processing_run_id="run-em-1",
            entity_type="ORGANIZATION",  # type: ignore[arg-type]
            target_mention_id="mention-10",
            candidate_mention_id="mention-20",
            target_value_display="Apex Supplies",
            candidate_value_display="Apex Supplies LLC",
            matching_method=EntityMatchingMethod.ORGANIZATION_NAME_SIMILARITY,
            match_classification=EntityMatchClassification.STRONG_CANDIDATE,
            match_score=0.92,
            score_semantics="token_set_ratio",
            decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
            evidence=EntityMatchEvidence(
                target_mention_id="mention-10",
                candidate_mention_id="mention-20",
                target_document_id="doc-inv-1",
                candidate_document_id="doc-po-1",
                target_page_number=1,
                candidate_page_number=1,
                target_field_key="supplier_name",
                candidate_field_key="supplier_name",
                matching_signals=["exact_base_token_match"],
                contradicting_signals=[],
            ),
        )
    ]


class TestEvidenceGraphProjector:
    """Validate graph assembly from heterogeneous domain records."""

    def test_complete_case_projection(self) -> None:
        """Verify all records project correctly into nodes and edges with provenance."""
        projector = EvidenceGraphProjector()
        case = _sample_case()
        docs = _sample_documents()
        ev_nodes = _sample_evidence()
        ffs = _sample_forensic_findings()
        cfs = _sample_consistency_findings()
        rels = _sample_relationships()
        matches = _sample_entity_matches()

        graph = projector.project_case(
            case=case,
            documents=docs,
            evidence_nodes=ev_nodes,
            forensic_findings=ffs,
            consistency_findings=cfs,
            detected_relationships=rels,
            entity_matches=matches,
        )

        # 1. Check node types present
        node_types = {n.node_type for n in graph.nodes.values()}
        assert GraphNodeType.CASE in node_types
        assert GraphNodeType.DOCUMENT in node_types
        assert GraphNodeType.EVIDENCE in node_types
        assert GraphNodeType.FORENSIC_FINDING in node_types
        assert GraphNodeType.CONSISTENCY_FINDING in node_types
        assert GraphNodeType.ORGANIZATION in node_types

        # 2. Check Case -> Document edges
        case_edges = [
            e
            for e in graph.edges.values()
            if e.predicate == GraphEdgePredicate.CONTAINS_DOCUMENT.value
        ]
        assert len(case_edges) == 2

        # 3. Check Document -> Evidence edges
        has_ev_edges = [
            e for e in graph.edges.values() if e.predicate == GraphEdgePredicate.HAS_EVIDENCE.value
        ]
        assert len(has_ev_edges) == 2

        # 4. Check Forensic Finding edges (PERTAINS_TO and SUPPORTED_BY)
        pertains_edges = [
            e for e in graph.edges.values() if e.predicate == GraphEdgePredicate.PERTAINS_TO.value
        ]
        assert len(pertains_edges) == 1

        ff_node_id = deterministic_node_id("case-uuid-001", GraphNodeType.FORENSIC_FINDING, "ff-1")
        ff_supp_edges = [
            e
            for e in graph.edges.values()
            if e.predicate == GraphEdgePredicate.SUPPORTED_BY.value
            and e.source_node_id == ff_node_id
        ]
        assert len(ff_supp_edges) >= 1

        # 5. Check Consistency Finding edges (COMPARES_DOCUMENT, SUPPORTED_BY, CONTRADICTED_BY)
        compares_edges = [
            e
            for e in graph.edges.values()
            if e.predicate == GraphEdgePredicate.COMPARES_DOCUMENT.value
        ]
        assert len(compares_edges) == 2  # compares doc-inv-1 and doc-po-1

        contra_edges = [
            e
            for e in graph.edges.values()
            if e.predicate == GraphEdgePredicate.CONTRADICTED_BY.value
        ]
        assert len(contra_edges) == 1
        assert contra_edges[0].status == RelationshipStatus.CONTRADICTED.value

        # 6. Check Detected Relationships preservation
        po_ref_edges = [
            e
            for e in graph.edges.values()
            if e.predicate == RelationshipType.REFERENCES_PURCHASE_ORDER.value
        ]
        assert len(po_ref_edges) == 1
        assert po_ref_edges[0].status == "CONFIRMED"

        invoiced_edges = [
            e for e in graph.edges.values() if e.predicate == RelationshipType.INVOICED.value
        ]
        assert len(invoiced_edges) == 1
        assert invoiced_edges[0].status == "CANDIDATE"

        # 7. Check Entity Match edges (MATCHES_IDENTITY)
        match_edges = [
            e
            for e in graph.edges.values()
            if e.predicate == GraphEdgePredicate.MATCHES_IDENTITY.value
        ]
        assert len(match_edges) == 1
        assert match_edges[0].status == MatchDecisionStatus.ALGORITHMIC_CANDIDATE.value

    def test_deterministic_repeatability(self) -> None:
        """Projecting identical records multiple times must produce identical IDs and edges."""
        projector = EvidenceGraphProjector()
        case = _sample_case()
        docs = _sample_documents()
        ev_nodes = _sample_evidence()
        ffs = _sample_forensic_findings()
        cfs = _sample_consistency_findings()
        rels = _sample_relationships()
        matches = _sample_entity_matches()

        g1 = projector.project_case(case, docs, ev_nodes, ffs, cfs, rels, matches)
        g2 = projector.project_case(case, docs, ev_nodes, ffs, cfs, rels, matches)

        assert set(g1.nodes.keys()) == set(g2.nodes.keys())
        assert set(g1.edges.keys()) == set(g2.edges.keys())

        for nid, node1 in g1.nodes.items():
            node2 = g2.nodes[nid]
            assert node1.label == node2.label
            assert node1.node_type == node2.node_type

        for eid, edge1 in g1.edges.items():
            edge2 = g2.edges[eid]
            assert edge1.predicate == edge2.predicate
            assert edge1.status == edge2.status
            assert edge1.source_node_id == edge2.source_node_id
            assert edge1.target_node_id == edge2.target_node_id

    def test_missing_or_orphan_records_handled_safely(self) -> None:
        """Orphan references must not cause crashes or broken edges."""
        projector = EvidenceGraphProjector()
        case = _sample_case()

        # Evidence referencing non-existent document
        orphan_ev = EvidenceNode(
            id="ev-orphan",
            case_id="case-uuid-001",
            document_id="doc-nonexistent",
            processing_run_id="run-x",
            evidence_type=EvidenceType.OCR_TEXT,
            title="Orphan Token",
            description="desc",
            source_component="ocr",
            source_version="1.0",
        )

        # Finding referencing non-existent evidence
        orphan_finding = ForensicFinding(
            id="ff-orphan",
            case_id="case-uuid-001",
            document_id="doc-nonexistent",
            processing_run_id="run-x",
            category=FindingCategory.PDF_STRUCTURE,
            title="Structural anomaly",
            description="desc",
            severity=FindingSeverity.LOW,
            evidence_ids=["ev-nonexistent"],
            source_component="pdf_structural",
        )

        graph = projector.project_case(
            case=case,
            documents=[],
            evidence_nodes=[orphan_ev],
            forensic_findings=[orphan_finding],
            consistency_findings=[],
            detected_relationships=[],
            entity_matches=[],
        )

        # Nodes exist, but invalid edges to missing docs/evidence were omitted cleanly
        assert any(n.source_entity_id == "ev-orphan" for n in graph.nodes.values())
        assert any(n.source_entity_id == "ff-orphan" for n in graph.nodes.values())
        # No edge exists pointing to missing doc-nonexistent
        for e in graph.edges.values():
            assert e.source_node_id in graph.nodes
            assert e.target_node_id in graph.nodes
