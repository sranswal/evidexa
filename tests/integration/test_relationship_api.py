"""Integration tests for cross-document relationship detection API, human review, and security guarantees."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.core.config import settings
from document_intelligence.core.exceptions import SecurityException
from document_intelligence.domain.enums import (
    AuditEventType,
    FieldDataType,
    RelationshipStatus,
    RelationshipType,
)
from document_intelligence.domain.identifiers import utc_now
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.infrastructure.persistence.models import (
    AuditEventModel,
    DetectedRelationshipModel,
)
from document_intelligence.infrastructure.storage.filesystem import (
    FilesystemDocumentStorage,
)
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.relationship_detection.service import (
    RelationshipDetectionService,
)
from tests.fixtures.ocr_factory import create_clean_digital_pdf


def _upload_pdf(
    client: TestClient, case_id: str, pdf_path: Path, filename: str = "doc.pdf"
) -> dict[str, Any]:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, f"Failed uploading PDF: {response.text}"
    return response.json()


class TestRelationshipApiIntegration:
    """End-to-end integration tests for cross-document relationship detection, review, and lifecycle."""

    def test_relationship_detection_end_to_end_and_audit(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify cross-document relationship detection workflow across invoice and receipt with audit trail."""
        # 1. Create case
        case_resp = client.post("/api/v1/cases", json={"title": "Relationship Detection Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Upload invoice and receipt documents
        pdf1 = tmp_path / "invoice_100.pdf"
        create_clean_digital_pdf(pdf1)
        _upload_pdf(client, case_id, pdf1, "invoice_100.pdf")

        pdf2 = tmp_path / "receipt_200.pdf"
        create_clean_digital_pdf(pdf2)
        doc2 = _upload_pdf(client, case_id, pdf2, "receipt_200.pdf")
        doc2_id = doc2["id"]

        # 3. Call detect directly via API with synthetic transactions
        detect_resp = client.post(
            f"/api/v1/cases/{case_id}/relationships",
            json={
                "synthetic_transactions": [
                    {
                        "transaction_id": "TX-100-SETTLE",
                        "statement_document_id": doc2_id,
                        "amount": "1500.00",
                        "currency": "USD",
                        "description": "Payment for INV-100",
                    }
                ]
            },
        )
        assert detect_resp.status_code == 201
        result_data = detect_resp.json()
        assert result_data["case_id"] == case_id
        assert "relationships" in result_data
        assert "unsupported_relationship_types" in result_data

        # 4. List runs
        runs_resp = client.get(f"/api/v1/cases/{case_id}/relationships/runs")
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        assert len(runs) >= 1
        run_id = runs[0]["id"]

        # 5. Get run result
        run_res_resp = client.get(f"/api/v1/cases/{case_id}/relationships/runs/{run_id}")
        assert run_res_resp.status_code == 200

        # 6. Get latest result
        latest_resp = client.get(f"/api/v1/cases/{case_id}/relationships/latest")
        assert latest_resp.status_code == 200

        # 7. List relationships with pagination and filtering
        rels_resp = client.get(f"/api/v1/cases/{case_id}/relationships?limit=10")
        assert rels_resp.status_code == 200
        rels_page = rels_resp.json()
        assert "items" in rels_page
        assert "total" in rels_page

        # 8. Verify audit ledger
        audit_events = (
            db_session.query(AuditEventModel)
            .filter(
                AuditEventModel.case_id == case_id,
                AuditEventModel.event_type == AuditEventType.RELATIONSHIPS_DETECTED.value,
            )
            .all()
        )
        assert len(audit_events) >= 1
        assert audit_events[0].event_hash is not None

    def test_human_review_workflow_and_audit(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify human review decisions preserve history without erasing detector evidence."""
        case_resp = client.post("/api/v1/cases", json={"title": "Review Relationship Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        pdf = tmp_path / "invoice_review.pdf"
        create_clean_digital_pdf(pdf)
        doc = _upload_pdf(client, case_id, pdf, "invoice_review.pdf")

        # Manually create a detected relationship in DB to test review lifecycle
        rel_model = DetectedRelationshipModel(
            id="rel-rev-test-01",
            case_id=case_id,
            detection_run_id="run-rev-01",
            relationship_type=RelationshipType.ISSUED_BY.value,
            source_id="ORG:TEST",
            source_type="ORGANIZATION",
            source_label="Test Vendor",
            target_id=doc["id"],
            target_type="INVOICE",
            target_label=doc["original_filename"],
            direction_display="Test Vendor --ISSUED_BY--> Invoice",
            status=RelationshipStatus.CANDIDATE.value,
            score=0.75,
            score_semantics="evidence_strength",
            detection_method="EXPLICIT_FIELD_REFERENCE",
            detection_version="1.0.0",
            status_rationale="Candidate relationship awaiting confirmation.",
            evidence_payload={
                "relationship_type": "ISSUED_BY",
                "source_id": "ORG:TEST",
                "target_id": doc["id"],
                "source_case_id": case_id,
                "score": 0.75,
                "score_semantics": "evidence_strength",
                "status": "CANDIDATE",
                "status_rationale": "Initial candidate.",
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db_session.add(rel_model)
        db_session.commit()

        # Step 1: Mark unresolved
        rev1_resp = client.post(
            f"/api/v1/cases/{case_id}/relationships/rel-rev-test-01/review",
            json={
                "decision": "MARK_UNRESOLVED",
                "reason": "Need supporting purchase order contract.",
                "reviewer_id": "inv_agent_01",
            },
        )
        assert rev1_resp.status_code == 200
        rev1_data = rev1_resp.json()
        assert rev1_data["status"] == "UNRESOLVED"

        # Step 2: Confirm relationship
        rev2_resp = client.post(
            f"/api/v1/cases/{case_id}/relationships/rel-rev-test-01/review",
            json={
                "decision": "CONFIRM_RELATIONSHIP",
                "reason": "Contract confirmed via external registry.",
                "reviewer_id": "senior_analyst",
            },
        )
        assert rev2_resp.status_code == 200
        rev2_data = rev2_resp.json()
        assert rev2_data["status"] == "CONFIRMED"

        # Step 3: Check review history
        hist_resp = client.get(f"/api/v1/cases/{case_id}/relationships/rel-rev-test-01/reviews")
        assert hist_resp.status_code == 200
        history = hist_resp.json()
        assert len(history) == 2
        assert history[0]["decision"] == "MARK_UNRESOLVED"
        assert history[0]["reviewer_id"] == "inv_agent_01"
        assert history[1]["decision"] == "CONFIRM_RELATIONSHIP"
        assert history[1]["reviewer_id"] == "senior_analyst"

        # Step 4: Verify audit events
        review_events = (
            db_session.query(AuditEventModel)
            .filter(
                AuditEventModel.case_id == case_id,
                AuditEventModel.event_type == AuditEventType.RELATIONSHIP_REVIEWED.value,
            )
            .all()
        )
        assert len(review_events) == 2

    def test_cross_case_isolation_and_archival_safeguards(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Requirement: Cross-case relationship access must return 404, archived cases reject writes with 422."""
        # Create Case A and Case B
        c_a = client.post("/api/v1/cases", json={"title": "Case Alpha"}).json()["id"]
        c_b = client.post("/api/v1/cases", json={"title": "Case Beta"}).json()["id"]

        pdf = tmp_path / "doc_alpha.pdf"
        create_clean_digital_pdf(pdf)
        doc_a = _upload_pdf(client, c_a, pdf, "doc_alpha.pdf")

        # Create relationship in Case A
        rel_model = DetectedRelationshipModel(
            id="rel-alpha-001",
            case_id=c_a,
            detection_run_id="run-alpha",
            relationship_type=RelationshipType.ISSUED_BY.value,
            source_id="ORG:ALPHA",
            source_type="ORGANIZATION",
            source_label="Alpha Vendor",
            target_id=doc_a["id"],
            target_type="INVOICE",
            target_label=doc_a["original_filename"],
            direction_display="Alpha Vendor --ISSUED_BY--> Invoice",
            status=RelationshipStatus.CONFIRMED.value,
            score=0.95,
            score_semantics="evidence_strength",
            detection_method="EXPLICIT_FIELD_REFERENCE",
            detection_version="1.0.0",
            status_rationale="Alpha test.",
            evidence_payload={
                "relationship_type": "ISSUED_BY",
                "source_id": "ORG:ALPHA",
                "target_id": doc_a["id"],
                "source_case_id": c_a,
                "score": 0.95,
                "score_semantics": "evidence_strength",
                "status": "CONFIRMED",
                "status_rationale": "Alpha test.",
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db_session.add(rel_model)
        db_session.commit()

        # 1. Cross-case query on Case B must return 404
        cross_get = client.get(f"/api/v1/cases/{c_b}/relationships/rel-alpha-001")
        assert cross_get.status_code == 404

        # 2. Cross-case review on Case B must return 404
        cross_rev = client.post(
            f"/api/v1/cases/{c_b}/relationships/rel-alpha-001/review",
            json={
                "decision": "REJECT_RELATIONSHIP",
                "reason": "Intruder attempt",
                "reviewer_id": "bad_actor",
            },
        )
        assert cross_rev.status_code == 404

        # 3. Archive Case A
        archive_resp = client.post(f"/api/v1/cases/{c_a}/archive")
        assert archive_resp.status_code in (200, 204)

        # 4. Triggering detection on archived Case A must return 422
        arch_post = client.post(f"/api/v1/cases/{c_a}/relationships", json={})
        assert arch_post.status_code == 422

        # 5. Submitting review on archived Case A must return 422
        arch_rev = client.post(
            f"/api/v1/cases/{c_a}/relationships/rel-alpha-001/review",
            json={
                "decision": "REJECT_RELATIONSHIP",
                "reason": "Late rejection",
                "reviewer_id": "analyst",
            },
        )
        assert arch_rev.status_code == 422

    def test_zero_pii_leakage_in_relationships_database_and_artifacts(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Requirement: Sensitive bank account numbers must remain strictly masked."""
        case_id = client.post("/api/v1/cases", json={"title": "PII Protection Case"}).json()["id"]

        pdf = tmp_path / "bank_stmt.pdf"
        create_clean_digital_pdf(pdf)
        doc = _upload_pdf(client, case_id, pdf, "bank_stmt.pdf")

        # Build service with a statement having masked account number
        storage = FilesystemDocumentStorage(settings)
        from document_intelligence.infrastructure.repositories.audit_repository import (
            AuditRepository,
        )
        from document_intelligence.infrastructure.repositories.case_repository import (
            CaseRepository,
        )
        from document_intelligence.infrastructure.repositories.document_repository import (
            DocumentRepository,
        )
        from document_intelligence.infrastructure.repositories.processing_run_repository import (
            ProcessingRunRepository,
        )
        from document_intelligence.infrastructure.repositories.relationship_repository import (
            RelationshipRepository,
        )
        from document_intelligence.modules.audit.ledger import AuditLedgerService

        audit_service = AuditLedgerService(AuditRepository(db_session))
        case_service = CaseService(
            case_repo=CaseRepository(db_session), audit_service=audit_service
        )
        service = RelationshipDetectionService(
            case_service=case_service,
            document_repo=DocumentRepository(db_session),
            run_repo=ProcessingRunRepository(db_session),
            relationship_repo=RelationshipRepository(db_session),
            storage=storage,
            audit_service=audit_service,
        )

        stmt_field_masked = ExtractedFieldValue(
            field_key="account_number_masked",
            label="Masked Account",
            normalized_value="****9876",
            data_type=FieldDataType.MASKED_STRING,
            source_document_id=doc["id"],
            source_page_number=1,
        )
        holder_field = ExtractedFieldValue(
            field_key="account_holder",
            label="Account Holder",
            normalized_value="John Doe",
            data_type=FieldDataType.STRING,
            source_document_id=doc["id"],
            source_page_number=1,
        )

        result = service.detect_relationships_for_case(
            case_id=case_id,
            provided_fields_by_doc={doc["id"]: [holder_field, stmt_field_masked]},
        )

        assert len(result.relationships) >= 1

        # Check DB rows for unmasked account numbers
        rows = (
            db_session.query(DetectedRelationshipModel)
            .filter(DetectedRelationshipModel.case_id == case_id)
            .all()
        )
        for r in rows:
            # Full 12+ digit account numbers must never exist in text
            assert "123456789012" not in r.direction_display
            assert "123456789012" not in r.status_rationale
            payload_str = json.dumps(r.evidence_payload)
            assert "123456789012" not in payload_str

        # Check stored JSON artifact
        art_path = storage.get_artifact_path(result.storage_artifact_key)
        art_text = art_path.read_text(encoding="utf-8")
        assert "123456789012" not in art_text
        assert "****9876" in art_text

    def test_artifact_tamper_detection(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Requirement: Storage artifact SHA-256 mismatch must trigger SecurityException upon retrieval."""
        case_id = client.post("/api/v1/cases", json={"title": "Tamper Test Case"}).json()["id"]

        pdf = tmp_path / "tamper_doc.pdf"
        create_clean_digital_pdf(pdf)
        _upload_pdf(client, case_id, pdf, "tamper_doc.pdf")

        storage = FilesystemDocumentStorage(settings)
        from document_intelligence.infrastructure.repositories.audit_repository import (
            AuditRepository,
        )
        from document_intelligence.infrastructure.repositories.case_repository import (
            CaseRepository,
        )
        from document_intelligence.infrastructure.repositories.document_repository import (
            DocumentRepository,
        )
        from document_intelligence.infrastructure.repositories.processing_run_repository import (
            ProcessingRunRepository,
        )
        from document_intelligence.infrastructure.repositories.relationship_repository import (
            RelationshipRepository,
        )
        from document_intelligence.modules.audit.ledger import AuditLedgerService

        audit_service = AuditLedgerService(AuditRepository(db_session))
        case_service = CaseService(
            case_repo=CaseRepository(db_session), audit_service=audit_service
        )
        service = RelationshipDetectionService(
            case_service=case_service,
            document_repo=DocumentRepository(db_session),
            run_repo=ProcessingRunRepository(db_session),
            relationship_repo=RelationshipRepository(db_session),
            storage=storage,
            audit_service=audit_service,
        )

        result = service.detect_relationships_for_case(case_id=case_id)
        run_id = result.detection_run_id

        # Verified reload succeeds with correct hash
        loaded = service.get_run_result(
            case_id=case_id,
            run_id=run_id,
            expected_sha256=result.storage_artifact_sha256,
        )
        assert loaded.detection_run_id == run_id

        # Reload with forged hash triggers SecurityException
        tampered_hash = "f" * 64
        with pytest.raises(SecurityException) as exc_info:
            service.get_run_result(case_id=case_id, run_id=run_id, expected_sha256=tampered_hash)
        assert "Artifact integrity violation" in str(exc_info.value)
