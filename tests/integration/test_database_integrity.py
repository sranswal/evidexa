"""Integration tests verifying database relational integrity, foreign key cascades, and unique constraints."""

import pytest
from sqlalchemy.exc import IntegrityError

from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.infrastructure.persistence.models import (
    AuditEventModel,
    CaseModel,
    DocumentModel,
    EvidenceNodeModel,
    FindingEvidenceLinkModel,
    ForensicFindingModel,
    InvestigationDossierModel,
)


class TestDatabaseIntegrity:
    """Verify SQLite foreign key enforcement, cascades, and unique constraints."""

    def test_foreign_key_violation_rejected(self, db_session) -> None:
        """Attempting to insert a document referencing a non-existent case must fail with IntegrityError."""
        invalid_doc = DocumentModel(
            id=generate_id(),
            case_id="non-existent-case-id",
            original_filename="fraud.pdf",
            media_type="application/pdf",
            file_extension=".pdf",
            file_size_bytes=1024,
            sha256="0" * 64,
            storage_key="invalid/key.pdf",
            created_at=utc_now(),
        )
        db_session.add(invalid_doc)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_cascade_delete_on_case(self, db_session) -> None:
        """Deleting a case must cascade delete its associated documents and audit events."""
        case_id = generate_id()
        case = CaseModel(
            id=case_id,
            case_reference=f"REF-{case_id[:8]}",
            title="Cascade Test Case",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db_session.add(case)
        db_session.commit()

        doc_id = generate_id()
        doc = DocumentModel(
            id=doc_id,
            case_id=case_id,
            original_filename="doc.pdf",
            media_type="application/pdf",
            file_extension=".pdf",
            file_size_bytes=512,
            sha256="1" * 64,
            storage_key=f"{case_id}/{doc_id}.pdf",
            created_at=utc_now(),
        )
        db_session.add(doc)
        db_session.commit()

        # Verify document exists
        assert db_session.get(DocumentModel, doc_id) is not None

        # Delete case
        db_session.delete(case)
        db_session.commit()

        # Verify document was cascade-deleted by database foreign key constraint
        assert db_session.get(DocumentModel, doc_id) is None

    def test_dossier_case_version_unique_constraint(self, db_session) -> None:
        """Creating two dossiers with identical (case_id, version) must violate unique constraint."""
        case_id = generate_id()
        case = CaseModel(
            id=case_id,
            case_reference=f"REF-{case_id[:8]}",
            title="Dossier Unique Test Case",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db_session.add(case)
        db_session.commit()

        d1 = InvestigationDossierModel(
            id=generate_id(),
            case_id=case_id,
            version=1,
            status="DRAFT",
            executive_summary="Summary 1",
            created_at=utc_now(),
            created_by="analyst-1",
        )
        db_session.add(d1)
        db_session.commit()

        d2 = InvestigationDossierModel(
            id=generate_id(),
            case_id=case_id,
            version=1,  # Duplicate version!
            status="DRAFT",
            executive_summary="Summary 2",
            created_at=utc_now(),
            created_by="analyst-2",
        )
        db_session.add(d2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_audit_event_sequence_unique_constraint(self, db_session) -> None:
        """Creating two audit events with duplicate (case_id, sequence_number) must fail."""
        case_id = generate_id()
        case = CaseModel(
            id=case_id,
            case_reference=f"REF-{case_id[:8]}",
            title="Audit Unique Test Case",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db_session.add(case)
        db_session.commit()

        e1 = AuditEventModel(
            id=generate_id(),
            case_id=case_id,
            sequence_number=1,
            event_type="CASE_CREATED",
            entity_type="CASE",
            entity_id=case_id,
            timestamp=utc_now(),
            payload={"step": 1},
            event_hash="hash_1" + "0" * 58,
        )
        db_session.add(e1)
        db_session.commit()

        e2 = AuditEventModel(
            id=generate_id(),
            case_id=case_id,
            sequence_number=1,  # Duplicate sequence number!
            event_type="DOCUMENT_INGESTED",
            entity_type="DOCUMENT",
            entity_id=generate_id(),
            timestamp=utc_now(),
            payload={"step": 2},
            event_hash="hash_2" + "0" * 58,
        )
        db_session.add(e2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_finding_evidence_links_relational_table(self, db_session) -> None:
        """Verify relational junction between forensic findings and evidence nodes."""
        case_id = generate_id()
        case = CaseModel(
            id=case_id,
            case_reference=f"REF-{case_id[:8]}",
            title="Links Test Case",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db_session.add(case)
        db_session.commit()

        finding_id = generate_id()
        finding = ForensicFindingModel(
            id=finding_id,
            case_id=case_id,
            processing_run_id=generate_id(),
            category="TAMPERING",
            title="ELA Anomaly Detected",
            description="High error variance in date block",
            severity="HIGH",
            status="PROPOSED",
            source_component="test-ela",
            created_at=utc_now(),
        )
        db_session.add(finding)

        evidence_id = generate_id()
        evidence = EvidenceNodeModel(
            id=evidence_id,
            case_id=case_id,
            processing_run_id=generate_id(),
            evidence_type="PIXEL_DIFFERENCE_MAP",
            title="ELA Map",
            description="Resaved JPEG difference overlay",
            source_component="test-ela",
            source_version="1.0",
            observed_at=utc_now(),
        )
        db_session.add(evidence)
        db_session.commit()

        # Link finding to evidence
        link = FindingEvidenceLinkModel(finding_id=finding_id, evidence_id=evidence_id)
        db_session.add(link)
        db_session.commit()

        persisted_link = db_session.get(FindingEvidenceLinkModel, (finding_id, evidence_id))
        assert persisted_link is not None

        # Verify foreign key constraint on link: invalid evidence_id fails
        invalid_link = FindingEvidenceLinkModel(
            finding_id=finding_id, evidence_id="invalid-evidence-id"
        )
        db_session.add(invalid_link)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
