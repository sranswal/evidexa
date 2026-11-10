"""Integration tests for Assistant REST API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import CaseStatus, IngestionStatus
from document_intelligence.domain.models.case import Case
from document_intelligence.domain.models.document import Document
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)


def test_assistant_api_case_isolation_not_found(client: TestClient) -> None:
    """Querying an unknown case ID must return 404 Not Found."""
    resp = client.post(
        "/api/v1/cases/unknown-case-id/assistant/query",
        json={"question": "What is in this case?"},
    )
    assert resp.status_code == 404


def test_assistant_api_context_summary(client: TestClient, db_session: Session) -> None:
    """GET /context-summary returns evidence counts and document list."""
    case_repo = CaseRepository(db_session)
    doc_repo = DocumentRepository(db_session)

    case = case_repo.save(Case(title="Context Summary Test", status=CaseStatus.ACTIVE))
    doc = Document(
        case_id=case.id,
        original_filename="receipt_99.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=512,
        sha256="c" * 64,
        storage_key="test/rec.pdf",
        ingestion_status=IngestionStatus.STORED,
    )
    doc_repo.save(doc)

    resp = client.get(f"/api/v1/cases/{case.id}/assistant/context-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == case.id
    assert data["counts"]["documents"] == 1
    assert "receipt_99.pdf" in data["document_titles"]


def test_assistant_api_query_lifecycle(client: TestClient, db_session: Session) -> None:
    """Full lifecycle query returning grounded response with citations."""
    case_repo = CaseRepository(db_session)
    doc_repo = DocumentRepository(db_session)

    case = case_repo.save(Case(title="Investigation Gamma", status=CaseStatus.ACTIVE))
    doc = Document(
        case_id=case.id,
        original_filename="invoice_alpha.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256="d" * 64,
        storage_key="test/inv.pdf",
        ingestion_status=IngestionStatus.STORED,
    )
    doc_repo.save(doc)

    resp = client.post(
        f"/api/v1/cases/{case.id}/assistant/query",
        json={
            "question": "Provide a case summary of all uploaded documents.",
            "category_hint": "INVESTIGATION_SUMMARY",
            "reviewer_id": "examiner-1",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["case_id"] == case.id
    assert data["question_category"] == "INVESTIGATION_SUMMARY"
    assert "invoice_alpha.pdf" in data["answer_text"] or len(data["observed_facts"]) >= 1
    assert len(data["citations"]) >= 1
    assert data["has_sufficient_evidence"] is True
    assert "AI-generated" in data["ai_notice"]


def test_assistant_api_read_only_on_archived_case(client: TestClient, db_session: Session) -> None:
    """Archived cases permit read-only querying of previously recorded evidence."""
    case_repo = CaseRepository(db_session)
    case = case_repo.save(Case(title="Archived Investigation", status=CaseStatus.ARCHIVED))

    resp = client.post(
        f"/api/v1/cases/{case.id}/assistant/query",
        json={"question": "What is the status of this archived case?"},
    )
    # Read-only query is permitted on archived case
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == case.id
