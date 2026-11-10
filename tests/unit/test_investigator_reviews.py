"""Unit tests for Investigator Reviews and Service Operations."""

from __future__ import annotations

import pytest

from document_intelligence.core.exceptions import NotFoundException, ValidationException
from document_intelligence.domain.enums import (
    AuditEventType,
    CaseStatus,
    DossierFormat,
    DossierStatus,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    InvestigatorReviewAction,
)
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
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.dossier.service import InvestigationDossierService


@pytest.fixture
def db_session():
    """In-memory SQLite session fixture."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from document_intelligence.infrastructure.persistence.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def dossier_service(db_session):
    audit_repo = AuditRepository(db_session)
    audit_service = AuditLedgerService(audit_repo)

    return InvestigationDossierService(
        case_repo=CaseRepository(db_session),
        document_repo=DocumentRepository(db_session),
        finding_repo=FindingRepository(db_session),
        consistency_repo=ConsistencyRepository(db_session),
        relationship_repo=RelationshipRepository(db_session),
        entity_match_repo=EntityMatchRepository(db_session),
        evidence_repo=EvidenceRepository(db_session),
        dossier_repo=DossierRepository(db_session),
        audit_service=audit_service,
    )


def test_record_finding_review_success_and_audit(db_session, dossier_service):
    # Setup case and finding
    case_repo = CaseRepository(db_session)
    finding_repo = FindingRepository(db_session)

    case = Case(
        id="case-rev-001",
        title="Review Audit Case",
        status=CaseStatus.ACTIVE,
    )
    case_repo.save(case)

    finding = ForensicFinding(
        id="ff-rev-101",
        case_id=case.id,
        processing_run_id="run-1",
        document_id="doc-1",
        category=FindingCategory.PDF_STRUCTURE,
        severity=FindingSeverity.HIGH,
        status=FindingStatus.DETECTED,
        title="Suspicious incremental trailer",
        description="Objects appended after EOF",
        confidence=0.9,
        source_component="pdf_structural_forensics",
        evidence_ids=["ev-node-1"],
    )
    finding_repo.save(finding)

    # Record review
    review = dossier_service.record_finding_review(
        case_id=case.id,
        finding_id=finding.id,
        reviewer_id="inv-lead-01",
        action=InvestigatorReviewAction.CONFIRM_OBSERVATION,
        rationale="Verified trailer xref corruption manually.",
    )

    assert review.id is not None
    assert review.finding_id == finding.id
    assert review.reviewer_id == "inv-lead-01"
    assert review.action == InvestigatorReviewAction.CONFIRM_OBSERVATION
    assert review.comment == "Verified trailer xref corruption manually."
    assert review.new_status == "CONFIRM_OBSERVATION"

    # Verify audit event
    audit_repo = AuditRepository(db_session)
    events, total = audit_repo.list_by_case(case.id)
    assert total >= 1
    review_events = [e for e in events if e.event_type == AuditEventType.REVIEW_DECISION_RECORDED]
    assert len(review_events) == 1
    assert review_events[0].entity_id == finding.id
    assert review_events[0].actor_id == "inv-lead-01"


def test_record_finding_review_validations(db_session, dossier_service):
    case_repo = CaseRepository(db_session)
    case = Case(id="case-val-001", title="Validation Case", status=CaseStatus.ACTIVE)
    case_repo.save(case)

    # Empty reviewer ID
    with pytest.raises(ValidationException, match="Reviewer ID cannot be empty"):
        dossier_service.record_finding_review(
            case_id=case.id,
            finding_id="ff-none",
            reviewer_id="   ",
            action=InvestigatorReviewAction.CONFIRM_OBSERVATION,
            rationale="Valid rationale",
        )

    # Empty rationale
    with pytest.raises(ValidationException, match="Review rationale cannot be empty"):
        dossier_service.record_finding_review(
            case_id=case.id,
            finding_id="ff-none",
            reviewer_id="inv-01",
            action=InvestigatorReviewAction.CONFIRM_OBSERVATION,
            rationale="   ",
        )

    # Non-existent finding
    with pytest.raises(NotFoundException, match="not found"):
        dossier_service.record_finding_review(
            case_id=case.id,
            finding_id="ff-nonexistent",
            reviewer_id="inv-01",
            action=InvestigatorReviewAction.CONFIRM_OBSERVATION,
            rationale="Valid rationale",
        )


def test_dossier_lifecycle_draft_finalize_and_export(db_session, dossier_service):
    case_repo = CaseRepository(db_session)
    doc_repo = DocumentRepository(db_session)

    case = Case(id="case-life-001", title="Lifecycle Case", status=CaseStatus.ACTIVE)
    case_repo.save(case)

    doc = Document(
        id="doc-life-1",
        case_id=case.id,
        original_filename="sample_invoice.pdf",
        storage_key=f"storage/{case.id}/sample_invoice.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=24000,
        page_count=1,
        sha256="4" * 64,
    )
    doc_repo.save(doc)

    # Generate draft dossier
    draft = dossier_service.generate_dossier(
        case_id=case.id,
        created_by="inv-author",
        scope_and_purpose="Quarterly accounting audit",
    )
    assert draft.status == DossierStatus.DRAFT
    assert draft.version == 1
    assert len(draft.sections) == 12

    # Finalize dossier
    finalized = dossier_service.finalize_dossier(
        case_id=case.id,
        dossier_id=draft.id,
        user_id="inv-supervisor",
    )
    assert finalized.status == DossierStatus.APPROVED
    assert finalized.content_hash is not None
    assert len(finalized.content_hash) == 64

    # Export PDF
    pdf_bytes, media_type, filename = dossier_service.export_dossier(
        case_id=case.id,
        dossier_id=finalized.id,
        export_format=DossierFormat.PDF,
        user_id="inv-supervisor",
    )
    assert media_type == "application/pdf"
    assert filename.endswith(".pdf")
    assert len(pdf_bytes) > 500

    # Export JSON
    json_bytes, media_type, filename = dossier_service.export_dossier(
        case_id=case.id,
        dossier_id=finalized.id,
        export_format=DossierFormat.JSON,
        user_id="inv-supervisor",
    )
    assert media_type == "application/json"
    assert filename.endswith(".json")
    assert len(json_bytes) > 200
