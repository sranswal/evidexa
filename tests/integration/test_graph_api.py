"""Integration tests for Evidence Graph REST API, node inspection, neighborhood, and path search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    ConsistencyOutcome,
    FindingCategory,
    FindingSeverity,
    GraphNodeType,
    RelationshipDetectionMethod,
    RelationshipStatus,
    RelationshipType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.identifiers import generate_id
from document_intelligence.domain.models.consistency import (
    ConsistencyFinding,
)
from document_intelligence.domain.models.graph import deterministic_node_id
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipEvidence,
)
from document_intelligence.infrastructure.repositories.consistency_repository import (
    ConsistencyRepository,
)
from document_intelligence.infrastructure.repositories.relationship_repository import (
    RelationshipRepository,
)
from tests.fixtures.ocr_factory import create_clean_digital_pdf


def _upload_pdf(client: TestClient, case_id: str, pdf_path: Path, filename: str) -> dict[str, Any]:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, f"Failed uploading PDF: {response.text}"
    return response.json()


class TestEvidenceGraphApiIntegration:
    """Validate REST API endpoints for unified Evidence Graph."""

    def test_get_case_graph_end_to_end(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify graph retrieval projects case, documents, findings, and relationships."""
        # 1. Create case
        case_resp = client.post("/api/v1/cases", json={"title": "Graph Investigation Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Upload two documents
        pdf1 = tmp_path / "invoice_g1.pdf"
        create_clean_digital_pdf(pdf1)
        doc1 = _upload_pdf(client, case_id, pdf1, "invoice_g1.pdf")

        pdf2 = tmp_path / "po_g1.pdf"
        create_clean_digital_pdf(pdf2)
        doc2 = _upload_pdf(client, case_id, pdf2, "po_g1.pdf")

        # 3. Seed a consistency finding
        consistency_repo = ConsistencyRepository(db_session)
        cf_id = generate_id()
        consistency_repo.save_finding(
            ConsistencyFinding(
                id=cf_id,
                case_id=case_id,
                analysis_run_id=generate_id(),
                rule_id="CONSISTENCY-B03-FINANCIALS",
                category=FindingCategory.CROSS_DOCUMENT_MISMATCH,
                title="PO Overrun Discrepancy",
                explanation="Invoice exceeds PO total",
                severity=FindingSeverity.HIGH,
                outcome=ConsistencyOutcome.INCONSISTENT,
                affected_document_ids=[doc1["id"], doc2["id"]],
                compared_fields=["total_amount"],
            )
        )

        # 4. Seed a detected relationship
        rel_repo = RelationshipRepository(db_session)
        rel_id = generate_id()
        rel_repo.save_relationship(
            DetectedRelationship(
                id=rel_id,
                case_id=case_id,
                detection_run_id=generate_id(),
                relationship_type=RelationshipType.REFERENCES_PURCHASE_ORDER,
                source_id=doc1["id"],
                source_type="DOCUMENT",
                source_label="invoice_g1.pdf",
                target_id=doc2["id"],
                target_type="DOCUMENT",
                target_label="po_g1.pdf",
                direction_display="invoice_g1.pdf --REFERENCES_PURCHASE_ORDER--> po_g1.pdf",
                status=RelationshipStatus.CONFIRMED,
                status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                score=0.98,
                score_semantics="exact_citation",
                detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                status_rationale="PO cited on invoice",
                evidence=RelationshipEvidence(
                    relationship_type=RelationshipType.REFERENCES_PURCHASE_ORDER,
                    source_id=doc1["id"],
                    target_id=doc2["id"],
                    source_case_id=case_id,
                    score=0.98,
                    score_semantics="exact_citation",
                    status=RelationshipStatus.CONFIRMED,
                    status_rationale="Explicit citation",
                ),
            )
        )
        db_session.commit()

        # 5. Query case graph
        graph_resp = client.get(f"/api/v1/cases/{case_id}/graph")
        assert graph_resp.status_code == 200
        data = graph_resp.json()

        assert data["case_id"] == case_id
        assert data["total_nodes"] >= 3  # Case + 2 Documents + 1 Consistency Finding
        assert (
            data["total_edges"] >= 3
        )  # Case -> Doc1, Case -> Doc2, REFERENCES_PO, COMPARES_DOC...

        node_types = {n["node_type"] for n in data["nodes"]}
        assert "CASE" in node_types
        assert "DOCUMENT" in node_types
        assert "CONSISTENCY_FINDING" in node_types

        # 6. Filter by node type
        doc_only_resp = client.get(f"/api/v1/cases/{case_id}/graph?node_types=DOCUMENT")
        assert doc_only_resp.status_code == 200
        doc_data = doc_only_resp.json()
        assert all(n["node_type"] == "DOCUMENT" for n in doc_data["nodes"])

    def test_get_graph_node_and_neighborhood(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify node detail and neighborhood inspection endpoints."""
        case_resp = client.post("/api/v1/cases", json={"title": "Neighborhood Case"})
        case_id = case_resp.json()["id"]

        pdf = tmp_path / "sample_doc.pdf"
        create_clean_digital_pdf(pdf)
        doc = _upload_pdf(client, case_id, pdf, "sample_doc.pdf")

        # Derive node ID for the document
        doc_node_id = deterministic_node_id(case_id, GraphNodeType.DOCUMENT, doc["id"])

        # 1. Retrieve single node
        node_resp = client.get(f"/api/v1/cases/{case_id}/graph/nodes/{doc_node_id}")
        assert node_resp.status_code == 200
        node_data = node_resp.json()
        assert node_data["node"]["id"] == doc_node_id
        assert node_data["node"]["label"] == "sample_doc.pdf"
        assert len(node_data["incoming_edges"]) >= 1  # From Case

        # 2. Retrieve neighborhood
        neighbor_resp = client.get(
            f"/api/v1/cases/{case_id}/graph/nodes/{doc_node_id}/neighbors?max_hops=1"
        )
        assert neighbor_resp.status_code == 200
        neighbor_data = neighbor_resp.json()
        assert neighbor_data["center_node_id"] == doc_node_id
        assert neighbor_data["hops"] == 1
        assert len(neighbor_data["nodes"]) >= 2  # Doc + Case

    def test_find_paths_endpoint(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify path search between case and uploaded document."""
        case_resp = client.post("/api/v1/cases", json={"title": "Path Search Case"})
        case_id = case_resp.json()["id"]

        pdf = tmp_path / "path_target.pdf"
        create_clean_digital_pdf(pdf)
        doc = _upload_pdf(client, case_id, pdf, "path_target.pdf")

        case_node_id = deterministic_node_id(case_id, GraphNodeType.CASE, case_id)
        doc_node_id = deterministic_node_id(case_id, GraphNodeType.DOCUMENT, doc["id"])

        paths_resp = client.get(
            f"/api/v1/cases/{case_id}/graph/paths?source_node_id={case_node_id}&target_node_id={doc_node_id}"
        )
        assert paths_resp.status_code == 200
        paths_data = paths_resp.json()
        assert paths_data["total_paths_found"] == 1
        assert paths_data["paths"][0]["length"] == 1

    def test_cross_case_isolation_and_archival_access(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Verify 404 for non-existent case and read-only access for archived case."""
        # Non-existent case returns 404
        fake_id = generate_id()
        resp = client.get(f"/api/v1/cases/{fake_id}/graph")
        assert resp.status_code == 404

        # Create and archive case
        case_resp = client.post("/api/v1/cases", json={"title": "Archived Case"})
        case_id = case_resp.json()["id"]

        archive_resp = client.post(f"/api/v1/cases/{case_id}/archive")
        assert archive_resp.status_code == 200

        # Read-only graph query is permitted on archived cases
        archived_graph_resp = client.get(f"/api/v1/cases/{case_id}/graph")
        assert archived_graph_resp.status_code == 200
        assert archived_graph_resp.json()["case_id"] == case_id
