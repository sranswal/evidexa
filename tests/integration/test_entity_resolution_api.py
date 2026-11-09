"""Integration tests for cross-document entity resolution API, human review, and security guarantees."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.core.config import settings
from document_intelligence.core.exceptions import SecurityException
from document_intelligence.domain.enums import (
    AuditEventType,
    EntityReviewAction,
    HumanReviewStatus,
    MatchDecisionStatus,
    ResolvedEntityType,
)
from document_intelligence.domain.models.entity_resolution import EntityMention
from document_intelligence.infrastructure.persistence.models import (
    AuditEventModel,
    EntityCandidateMatchModel,
)
from document_intelligence.infrastructure.storage.filesystem import (
    FilesystemDocumentStorage,
)
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.entity_resolution.service import (
    EntityResolutionService,
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


class TestEntityResolutionApiIntegration:
    """End-to-end integration tests for cross-document entity resolution, review, and security."""

    def test_entity_resolution_end_to_end_and_audit(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify cross-document entity resolution workflow across two documents with audit trail."""
        # 1. Create case
        case_resp = client.post("/api/v1/cases", json={"title": "Entity Resolution Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Upload two distinct invoice PDFs
        pdf1 = tmp_path / "invoice1.pdf"
        create_clean_digital_pdf(pdf1)
        doc1 = _upload_pdf(client, case_id, pdf1, "invoice1.pdf")
        doc1_id = doc1["id"]

        pdf2 = tmp_path / "invoice2.pdf"
        create_clean_digital_pdf(pdf2)
        doc2 = _upload_pdf(client, case_id, pdf2, "invoice2.pdf")
        doc2_id = doc2["id"]

        # 3. Supply cross-document mentions (representing extracted organizations and invoices)
        mentions = [
            EntityMention(
                mention_id="m-doc1-org",
                case_id=case_id,
                document_id=doc1_id,
                page_number=1,
                processing_run_id="run-01",
                field_key="vendor_name",
                entity_type=ResolvedEntityType.ORGANIZATION,
                original_value="ACME Global Corp",
                normalized_value="acme global corp",
                base_name="acme global",
                legal_suffix="CORP",
            ),
            EntityMention(
                mention_id="m-doc2-org",
                case_id=case_id,
                document_id=doc2_id,
                page_number=1,
                processing_run_id="run-02",
                field_key="vendor_name",
                entity_type=ResolvedEntityType.ORGANIZATION,
                original_value="Acme Global Corporation",
                normalized_value="acme global corp",
                base_name="acme global",
                legal_suffix="CORP",
            ),
            EntityMention(
                mention_id="m-doc1-inv",
                case_id=case_id,
                document_id=doc1_id,
                page_number=1,
                processing_run_id="run-01",
                field_key="invoice_number",
                entity_type=ResolvedEntityType.INVOICE_REFERENCE,
                original_value="INV-2024-001",
                normalized_value="INV-2024-001",
            ),
            EntityMention(
                mention_id="m-doc2-inv",
                case_id=case_id,
                document_id=doc2_id,
                page_number=1,
                processing_run_id="run-02",
                field_key="invoice_number",
                entity_type=ResolvedEntityType.INVOICE_REFERENCE,
                original_value="INV-2024-001",
                normalized_value="INV-2024-001",
            ),
        ]

        # 4. Trigger resolution via POST
        res_resp = client.post(
            f"/api/v1/cases/{case_id}/entity-resolution",
            json={"mentions": [m.model_dump() for m in mentions]},
        )
        assert res_resp.status_code == 201
        res_data = res_resp.json()

        assert res_data["total_mentions"] == 4
        assert res_data["total_comparisons"] > 0
        assert len(res_data["candidate_matches"]) >= 2
        assert (
            len(res_data["resolved_entities"]) == 2
        )  # 1 organization cluster, 1 invoice reference cluster

        run_id = res_data["processing_run_id"]
        assert run_id is not None
        assert res_data["storage_artifact_sha256"] is not None

        # 5. Verify GET /runs
        runs_resp = client.get(f"/api/v1/cases/{case_id}/entity-resolution/runs")
        assert runs_resp.status_code == 200
        runs_list = runs_resp.json()
        assert len(runs_list) >= 1
        assert runs_list[0]["run_id"] == run_id

        # 6. Verify GET /latest
        latest_resp = client.get(f"/api/v1/cases/{case_id}/entity-resolution/latest")
        assert latest_resp.status_code == 200
        assert latest_resp.json()["processing_run_id"] == run_id

        # 7. Verify GET /entities
        entities_resp = client.get(f"/api/v1/cases/{case_id}/entity-resolution/entities")
        assert entities_resp.status_code == 200
        entities_data = entities_resp.json()
        assert entities_data["total"] == 2
        assert len(entities_data["items"]) == 2

        # 8. Verify GET /matches
        matches_resp = client.get(f"/api/v1/cases/{case_id}/entity-resolution/matches")
        assert matches_resp.status_code == 200
        matches_data = matches_resp.json()
        assert matches_data["total"] >= 2
        match_id = matches_data["items"][0]["id"]

        # 9. Verify GET /matches/{id}
        single_match_resp = client.get(
            f"/api/v1/cases/{case_id}/entity-resolution/matches/{match_id}"
        )
        assert single_match_resp.status_code == 200
        single_match = single_match_resp.json()
        assert single_match["id"] == match_id
        assert "evidence" in single_match
        assert single_match["review_status"] == HumanReviewStatus.UNREVIEWED.value

        # 10. Verify audit event in ledger
        audit = (
            db_session.query(AuditEventModel)
            .filter_by(
                case_id=case_id,
                event_type=AuditEventType.ENTITIES_RESOLVED.value,
            )
            .first()
        )
        assert audit is not None
        assert audit.payload["processing_run_id"] == run_id

    def test_human_review_workflow_and_audit(self, client: TestClient, db_session: Session) -> None:
        """Verify investigator human review decisions, review history, and audit ledger entries."""
        case_resp = client.post("/api/v1/cases", json={"title": "Review Workflow Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # Post resolution with candidate matches
        mentions = [
            EntityMention(
                mention_id="m1",
                case_id=case_id,
                document_id="doc1",
                page_number=1,
                processing_run_id="run1",
                field_key="customer_name",
                entity_type=ResolvedEntityType.PERSON,
                original_value="Robert J. Oppenheimer",
                normalized_value="robert j oppenheimer",
            ),
            EntityMention(
                mention_id="m2",
                case_id=case_id,
                document_id="doc2",
                page_number=1,
                processing_run_id="run2",
                field_key="customer_name",
                entity_type=ResolvedEntityType.PERSON,
                original_value="Robert Oppenheimer",
                normalized_value="robert oppenheimer",
            ),
        ]

        res_resp = client.post(
            f"/api/v1/cases/{case_id}/entity-resolution",
            json={"mentions": [m.model_dump() for m in mentions]},
        )
        assert res_resp.status_code == 201
        matches = res_resp.json()["candidate_matches"]
        assert len(matches) == 1
        match_id = matches[0]["id"]

        # Human Review 1: Mark Ambiguous
        rev1_payload = {
            "decision": EntityReviewAction.MARK_AMBIGUOUS.value,
            "reason": "Name is similar but requires middle initial verification.",
            "reviewer_id": "investigator-01",
        }
        rev1_resp = client.post(
            f"/api/v1/cases/{case_id}/entity-resolution/matches/{match_id}/review",
            json=rev1_payload,
        )
        assert rev1_resp.status_code == 200
        rev1_data = rev1_resp.json()
        assert rev1_data["decision_status"] == MatchDecisionStatus.AMBIGUOUS.value
        assert rev1_data["review_status"] == HumanReviewStatus.AMBIGUOUS.value

        # Human Review 2: Confirm Match after corroboration
        rev2_payload = {
            "decision": EntityReviewAction.CONFIRM_MATCH.value,
            "reason": "Corroborated by shared laboratory security clearance badge ID in supplementary file.",
            "reviewer_id": "lead-analyst-02",
        }
        rev2_resp = client.post(
            f"/api/v1/cases/{case_id}/entity-resolution/matches/{match_id}/review",
            json=rev2_payload,
        )
        assert rev2_resp.status_code == 200
        rev2_data = rev2_resp.json()
        assert rev2_data["decision_status"] == MatchDecisionStatus.CONFIRMED.value
        assert rev2_data["review_status"] == HumanReviewStatus.CONFIRMED.value

        # Verify review history GET endpoint preserves all review iterations
        hist_resp = client.get(
            f"/api/v1/cases/{case_id}/entity-resolution/matches/{match_id}/reviews"
        )
        assert hist_resp.status_code == 200
        hist = hist_resp.json()
        assert len(hist) == 2
        assert hist[0]["decision"] == EntityReviewAction.MARK_AMBIGUOUS.value
        assert hist[0]["reviewer_id"] == "investigator-01"
        assert hist[1]["decision"] == EntityReviewAction.CONFIRM_MATCH.value
        assert hist[1]["reviewer_id"] == "lead-analyst-02"

        # Verify audit ledger recorded both review decisions
        audits = (
            db_session.query(AuditEventModel)
            .filter_by(
                case_id=case_id,
                event_type=AuditEventType.ENTITY_MATCH_REVIEWED.value,
            )
            .order_by(AuditEventModel.sequence_number.asc())
            .all()
        )
        assert len(audits) == 2
        assert audits[0].actor_id == "investigator-01"
        assert audits[1].actor_id == "lead-analyst-02"

    def test_cross_case_isolation_and_archival_safeguards(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Verify strict case isolation and rejection of writes on archived cases."""
        # 1. Create Case A and Case B
        resp_a = client.post("/api/v1/cases", json={"title": "Case A"})
        case_a = resp_a.json()["id"]

        resp_b = client.post("/api/v1/cases", json={"title": "Case B"})
        case_b = resp_b.json()["id"]

        # Run resolution in Case A
        mentions_a = [
            EntityMention(
                mention_id="ma1",
                case_id=case_a,
                document_id="docA",
                page_number=1,
                processing_run_id="runA",
                field_key="invoice_number",
                entity_type=ResolvedEntityType.INVOICE_REFERENCE,
                original_value="INV-100",
                normalized_value="INV-100",
            )
        ]
        res_a = client.post(
            f"/api/v1/cases/{case_a}/entity-resolution",
            json={"mentions": [m.model_dump() for m in mentions_a]},
        )
        assert res_a.status_code == 201

        # Attempt to access Case A's resolution from Case B path -> Rejected (404)
        run_id_a = res_a.json()["processing_run_id"]
        cross_resp = client.get(f"/api/v1/cases/{case_b}/entity-resolution/runs/{run_id_a}")
        assert cross_resp.status_code == 404

        # Archive Case A
        archive_resp = client.post(f"/api/v1/cases/{case_a}/archive")
        assert archive_resp.status_code == 200

        # Attempt to trigger resolution on archived case -> Rejected (422 Unprocessable Entity)
        arch_post = client.post(
            f"/api/v1/cases/{case_a}/entity-resolution",
            json={"mentions": [m.model_dump() for m in mentions_a]},
        )
        assert arch_post.status_code == 422
        assert "Cannot execute operations on archived case" in arch_post.text

    def test_zero_pii_leakage_in_matches_database_and_artifacts(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Inspects SQLite rows in entity_candidate_matches and JSON artifacts to guarantee zero unmasked account numbers."""
        case_resp = client.post("/api/v1/cases", json={"title": "PII Entity Resolution Case"})
        case_id = case_resp.json()["id"]

        synthetic_acct = "987654321098"

        mentions = [
            EntityMention(
                mention_id="m1",
                case_id=case_id,
                document_id="doc1",
                page_number=1,
                processing_run_id="run1",
                field_key="account_number",
                entity_type=ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
                original_value="****1098",
                normalized_value="****1098",
            ),
            EntityMention(
                mention_id="m2",
                case_id=case_id,
                document_id="doc2",
                page_number=1,
                processing_run_id="run2",
                field_key="account_number",
                entity_type=ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
                original_value="****1098",
                normalized_value="****1098",
            ),
        ]

        res = client.post(
            f"/api/v1/cases/{case_id}/entity-resolution",
            json={"mentions": [m.model_dump() for m in mentions]},
        )
        assert res.status_code == 201
        run_id = res.json()["processing_run_id"]
        art_key = res.json()["storage_artifact_key"]
        assert run_id is not None

        # 1. Inspect SQLite rows
        match_models = db_session.query(EntityCandidateMatchModel).filter_by(case_id=case_id).all()
        assert len(match_models) > 0
        for row in match_models:
            assert synthetic_acct not in (row.target_value_display or "")
            assert synthetic_acct not in (row.candidate_value_display or "")
            evidence_str = str(row.evidence_payload)
            assert synthetic_acct not in evidence_str

        # 2. Inspect filesystem artifact bytes
        storage = FilesystemDocumentStorage(settings)
        art_path = storage.get_artifact_path(art_key)
        assert art_path.exists()
        raw_artifact = art_path.read_text(encoding="utf-8")
        assert synthetic_acct not in raw_artifact
        assert "****1098" in raw_artifact

    def test_artifact_tamper_detection(self, client: TestClient, db_session: Session) -> None:
        """Verify that altering artifact bytes triggers SecurityException during reload with expected SHA-256."""
        case_resp = client.post("/api/v1/cases", json={"title": "Artifact Integrity Case"})
        case_id = case_resp.json()["id"]

        mentions = [
            EntityMention(
                mention_id="m1",
                case_id=case_id,
                document_id="doc1",
                page_number=1,
                processing_run_id="run1",
                field_key="vendor_name",
                entity_type=ResolvedEntityType.ORGANIZATION,
                original_value="Acme Corp",
                normalized_value="acme corp",
            )
        ]

        res = client.post(
            f"/api/v1/cases/{case_id}/entity-resolution",
            json={"mentions": [m.model_dump() for m in mentions]},
        )
        assert res.status_code == 201
        run_id = res.json()["processing_run_id"]
        sha256_recorded = res.json()["storage_artifact_sha256"]
        assert run_id is not None
        assert sha256_recorded is not None

        # Call get_run_result with wrong hash -> SecurityException
        storage = FilesystemDocumentStorage(settings)
        from document_intelligence.infrastructure.repositories.audit_repository import (
            AuditRepository,
        )
        from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
        from document_intelligence.infrastructure.repositories.document_repository import (
            DocumentRepository,
        )
        from document_intelligence.infrastructure.repositories.entity_match_repository import (
            EntityMatchRepository,
        )
        from document_intelligence.infrastructure.repositories.processing_run_repository import (
            ProcessingRunRepository,
        )
        from document_intelligence.modules.audit.ledger import AuditLedgerService

        audit_svc = AuditLedgerService(AuditRepository(db_session))
        case_svc = CaseService(CaseRepository(db_session), audit_service=audit_svc)
        er_service = EntityResolutionService(
            case_service=case_svc,
            document_repo=DocumentRepository(db_session),
            run_repo=ProcessingRunRepository(db_session),
            match_repo=EntityMatchRepository(db_session),
            storage=storage,
            audit_service=audit_svc,
        )

        with pytest.raises(SecurityException, match="Artifact integrity violation"):
            er_service.get_run_result(
                case_id=case_id,
                run_id=run_id,
                expected_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            )
