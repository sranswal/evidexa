"""Unit tests for AssistantService application coordinator."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    AssistantQuestionCategory,
    AuditEventType,
    CaseStatus,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    IngestionStatus,
)
from document_intelligence.domain.identifiers import generate_id
from document_intelligence.domain.models.assistant import AssistantQueryRequest
from document_intelligence.domain.models.case import Case
from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.infrastructure.repositories.audit_repository import AuditRepository
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.consistency_repository import (
    ConsistencyRepository,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.dossier_repository import (
    DossierRepository,
)
from document_intelligence.infrastructure.repositories.entity_match_repository import (
    EntityMatchRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.finding_repository import (
    FindingRepository,
)
from document_intelligence.infrastructure.repositories.relationship_repository import (
    RelationshipRepository,
)
from document_intelligence.modules.assistant.provider import MockLlmProvider
from document_intelligence.modules.assistant.retriever import CaseEvidenceRetriever
from document_intelligence.modules.assistant.service import AssistantService
from document_intelligence.modules.audit.ledger import AuditLedgerService


@pytest.fixture
def service_bundle(db_session: Session) -> tuple[AssistantService, Case, Document, ForensicFinding]:
    case_repo = CaseRepository(db_session)
    doc_repo = DocumentRepository(db_session)
    finding_repo = FindingRepository(db_session)
    audit_repo = AuditRepository(db_session)

    case = case_repo.save(Case(title="Operation Trident", status=CaseStatus.ACTIVE))
    doc = Document(
        case_id=case.id,
        original_filename="bank_statement_nov.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=4096,
        sha256="b" * 64,
        storage_key="test/bank.pdf",
        page_count=3,
        ingestion_status=IngestionStatus.STORED,
    )
    doc_repo.save(doc)

    finding = ForensicFinding(
        case_id=case.id,
        document_id=doc.id,
        processing_run_id=generate_id(),
        category=FindingCategory.PDF_STRUCTURE,
        title="Hidden stream detected",
        description="Stream dictionary with length mismatch found in page 2.",
        severity=FindingSeverity.MEDIUM,
        categorical_confidence="high",
        confidence_source="pikepdf",
        source_component="pdf-structural-analyzer",
        evidence_ids=["ev-node-1"],
        status=FindingStatus.DETECTED,
    )
    finding_repo.save(finding)

    retriever = CaseEvidenceRetriever(
        case_repo=case_repo,
        document_repo=doc_repo,
        finding_repo=finding_repo,
        consistency_repo=ConsistencyRepository(db_session),
        relationship_repo=RelationshipRepository(db_session),
        entity_match_repo=EntityMatchRepository(db_session),
        evidence_repo=EvidenceRepository(db_session),
        dossier_repo=DossierRepository(db_session),
    )

    audit_service = AuditLedgerService(audit_repo)
    provider = MockLlmProvider()
    service = AssistantService(retriever=retriever, provider=provider, audit_service=audit_service)

    return service, case, doc, finding


def test_assistant_query_generates_grounded_response_with_citations(
    service_bundle: tuple[AssistantService, Case, Document, ForensicFinding],
    db_session: Session,
) -> None:
    service, case, doc, finding = service_bundle

    req = AssistantQueryRequest(
        question="Explain the structural finding for this case",
        category_hint=AssistantQuestionCategory.EVIDENCE_EXPLANATION,
        reviewer_id="senior-examiner",
    )

    resp = service.query(case_id=case.id, request=req)

    assert resp.case_id == case.id
    assert resp.question_category == AssistantQuestionCategory.EVIDENCE_EXPLANATION
    assert len(resp.citations) >= 1
    # Check that citation has valid target_route
    assert any(
        c.target_route == f"/cases/{case.id}/documents/{doc.id}/examine" for c in resp.citations
    )
    assert resp.has_sufficient_evidence is True
    assert "EVIDEXA" in resp.ai_notice or "AI-generated" in resp.ai_notice

    # Verify audit event was logged
    audit_repo = AuditRepository(db_session)
    events, total = audit_repo.list_by_case(case_id=case.id, limit=50)
    assert any(e.event_type == AuditEventType.ASSISTANT_QUERY_EXECUTED for e in events)


def test_assistant_handles_provider_timeout_gracefully(
    service_bundle: tuple[AssistantService, Case, Document, ForensicFinding],
) -> None:
    _, case, _, _ = service_bundle

    # Replace provider with timeout simulator
    timeout_provider = MockLlmProvider(simulate_timeout=True)
    failing_service = AssistantService(
        retriever=service_bundle[0].retriever,
        provider=timeout_provider,
        audit_service=service_bundle[0].audit_service,
    )

    req = AssistantQueryRequest(question="What is the summary?")
    resp = failing_service.query(case_id=case.id, request=req)

    assert resp.has_sufficient_evidence is False
    assert "timeout" in resp.answer_text.lower() or "error" in resp.answer_text.lower()
    assert len(resp.limitations) >= 1


def test_assistant_handles_malformed_json_output_gracefully(
    service_bundle: tuple[AssistantService, Case, Document, ForensicFinding],
) -> None:
    _, case, _, _ = service_bundle

    malformed_provider = MockLlmProvider(simulate_malformed=True)
    resilient_service = AssistantService(
        retriever=service_bundle[0].retriever,
        provider=malformed_provider,
        audit_service=service_bundle[0].audit_service,
    )

    req = AssistantQueryRequest(question="Compare values")
    resp = resilient_service.query(case_id=case.id, request=req)

    assert resp.has_sufficient_evidence is False
    assert "malformed" in resp.answer_text.lower() or "error" in resp.answer_text.lower()


def test_assistant_context_summary(
    service_bundle: tuple[AssistantService, Case, Document, ForensicFinding],
) -> None:
    service, case, doc, _ = service_bundle

    summary = service.get_context_summary(case_id=case.id)
    assert summary["case_id"] == case.id
    assert summary["counts"]["documents"] == 1
    assert summary["counts"]["forensic_findings"] == 1
    assert doc.original_filename in summary["document_titles"]
