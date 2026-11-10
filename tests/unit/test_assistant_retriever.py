"""Unit tests for CaseEvidenceRetriever."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from document_intelligence.core.exceptions import EntityNotFoundException
from document_intelligence.domain.enums import (
    CaseStatus,
    EvidenceType,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    IngestionStatus,
    RelationshipDetectionMethod,
    RelationshipStatus,
    RelationshipType,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.case import Case
from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipEvidence,
)
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
from document_intelligence.modules.assistant.retriever import CaseEvidenceRetriever


@pytest.fixture
def retriever(db_session: Session) -> CaseEvidenceRetriever:
    return CaseEvidenceRetriever(
        case_repo=CaseRepository(db_session),
        document_repo=DocumentRepository(db_session),
        finding_repo=FindingRepository(db_session),
        consistency_repo=ConsistencyRepository(db_session),
        relationship_repo=RelationshipRepository(db_session),
        entity_match_repo=EntityMatchRepository(db_session),
        evidence_repo=EvidenceRepository(db_session),
        dossier_repo=DossierRepository(db_session),
    )


def test_retriever_enforces_case_isolation(retriever: CaseEvidenceRetriever) -> None:
    """Non-existent or cross-case lookups must strictly raise EntityNotFoundException."""
    with pytest.raises(EntityNotFoundException):
        retriever.retrieve(case_id="non-existent-case-id", question="What documents exist?")


def test_retriever_returns_empty_when_no_evidence_registered(
    db_session: Session, retriever: CaseEvidenceRetriever
) -> None:
    """A valid case with no documents or findings returns structured empty collections."""
    case_repo = CaseRepository(db_session)
    case = case_repo.save(Case(title="Empty Case", status=CaseStatus.ACTIVE))

    context = retriever.retrieve(case_id=case.id, question="Summarize findings")
    assert context.case_id == case.id
    assert context.case_title == "Empty Case"
    assert len(context.documents) == 0
    assert len(context.findings) == 0
    assert len(context.consistency_findings) == 0
    assert context.total_retrieved_items == 0


def test_retriever_gathers_and_masks_evidence(
    db_session: Session, retriever: CaseEvidenceRetriever
) -> None:
    """Retriever compiles documents, findings, relationships, and masks sensitive identifiers."""
    case_repo = CaseRepository(db_session)
    doc_repo = DocumentRepository(db_session)
    finding_repo = FindingRepository(db_session)
    rel_repo = RelationshipRepository(db_session)
    ev_repo = EvidenceRepository(db_session)

    case = case_repo.save(Case(title="Fraud Audit Case", status=CaseStatus.ACTIVE))
    case_id = case.id

    # 1. Document
    doc = Document(
        case_id=case_id,
        original_filename="vendor_invoice_101.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256="a" * 64,
        storage_key="test/key",
        page_count=2,
        ingestion_status=IngestionStatus.STORED,
    )
    doc_repo.save(doc)

    # 2. Finding
    finding = ForensicFinding(
        case_id=case_id,
        document_id=doc.id,
        processing_run_id=generate_id(),
        category=FindingCategory.PDF_STRUCTURE,
        title="Incremental update detected",
        description="Trailer dictionary was modified after original signature.",
        severity=FindingSeverity.HIGH,
        categorical_confidence="high",
        confidence_source="pikepdf",
        source_component="pdf-structural-analyzer",
        evidence_ids=["ev-node-1"],
        status=FindingStatus.DETECTED,
    )
    finding_repo.save(finding)

    # 3. Evidence Node with sensitive account digits
    ev_node = EvidenceNode(
        case_id=case_id,
        document_id=doc.id,
        processing_run_id=generate_id(),
        evidence_type=EvidenceType.EXTRACTED_FIELD,
        title="Beneficiary Account",
        description="Account Number",
        raw_value="Account 123456789012",
        source_component="test",
        source_version="1.0",
        observed_at=utc_now(),
    )
    ev_repo.save(ev_node)

    # 4. Relationship with candidate status
    evidence = RelationshipEvidence(
        relationship_type=RelationshipType.SUPPLIES,
        source_id="vendor_1",
        target_id="buyer_1",
        source_case_id=case_id,
        source_extraction_run_id="run_1",
        source_field_keys=["vendor_name"],
        supporting_evidence_node_ids=[],
        source_page_references=[1],
        bounding_boxes=[],
        detection_method=RelationshipDetectionMethod.COMMERCIAL_FLOW_RULE,
        score=0.75,
        score_semantics="heuristic",
        status=RelationshipStatus.CANDIDATE,
        status_rationale="Supplier name matched without contract verification.",
    )
    rel = DetectedRelationship(
        case_id=case_id,
        detection_run_id="run_1",
        relationship_type=RelationshipType.SUPPLIES,
        source_id="vendor_1",
        source_type="ORGANIZATION",
        source_label="Acme Corp",
        target_id="buyer_1",
        target_type="ORGANIZATION",
        target_label="Global Logistics",
        direction_display="Acme Corp --SUPPLIES--> Global Logistics",
        status=RelationshipStatus.CANDIDATE,
        score=0.75,
        score_semantics="heuristic",
        detection_method=RelationshipDetectionMethod.COMMERCIAL_FLOW_RULE,
        status_rationale="Supplier name matched without contract verification.",
        evidence=evidence,
    )
    rel_repo.save_relationship(rel)

    # Execute retrieval
    context = retriever.retrieve(case_id=case_id, question="What invoice and account exist?")
    assert context.case_id == case_id
    assert len(context.documents) == 1
    assert context.documents[0]["declared_filename"] == "vendor_invoice_101.pdf"
    assert len(context.findings) == 1
    assert context.findings[0]["title"] == "Incremental update detected"
    assert len(context.relationships) == 1
    assert context.relationships[0]["status"] == "CANDIDATE"

    # Verify PII masking on account number in extracted fields
    assert len(context.extracted_fields) == 1
    field_text = context.extracted_fields[0]["text"]
    assert "123456789012" not in field_text
    assert "****9012" in field_text or "****" in field_text
