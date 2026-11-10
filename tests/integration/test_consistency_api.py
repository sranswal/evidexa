"""Integration tests for Cross-Document Consistency Engine REST API, human reviews, and security safeguards."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    AuditEventType,
    ConsistencyOutcome,
    ConsistencyReviewAction,
    FindingStatus,
)
from document_intelligence.infrastructure.persistence.models import (
    AuditEventModel,
)
from document_intelligence.infrastructure.repositories.consistency_repository import (
    ConsistencyRepository,
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


class TestConsistencyApiIntegration:
    """End-to-end integration tests for cross-document consistency API, review workflows, and isolation."""

    def test_consistency_analysis_end_to_end_and_audit(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify full consistency analysis run, artifact storage, and audit trail."""
        # 1. Create active case
        case_resp = client.post("/api/v1/cases", json={"title": "Consistency Investigation Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Upload invoice and receipt documents
        pdf1 = tmp_path / "invoice_1.pdf"
        create_clean_digital_pdf(pdf1)
        _upload_pdf(client, case_id, pdf1, "invoice_1.pdf")

        pdf2 = tmp_path / "receipt_1.pdf"
        create_clean_digital_pdf(pdf2)
        doc2 = _upload_pdf(client, case_id, pdf2, "receipt_1.pdf")
        doc2_id = doc2["id"]

        # 3. Trigger consistency analysis
        analyze_resp = client.post(
            f"/api/v1/cases/{case_id}/consistency/analyze",
            json={
                "monetary_tolerance": "0.00",
                "parameters": {
                    "transactions": [
                        {
                            "amount": "1500.00",
                            "currency": "USD",
                            "description": "Payment for INV-1",
                            "reference": "TX-999",
                            "bank_statement_id": doc2_id,
                        }
                    ]
                },
            },
        )
        assert analyze_resp.status_code == 201
        res = analyze_resp.json()
        assert res["case_id"] == case_id
        assert "analysis_run_id" in res
        assert "status" in res
        assert res["status"] == "SUCCEEDED"
        assert res["storage_artifact_key"] is not None
        assert res["storage_artifact_sha256"] is not None
        run_id = res["analysis_run_id"]

        # 4. List runs
        runs_resp = client.get(f"/api/v1/cases/{case_id}/consistency/runs")
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        assert len(runs) >= 1
        assert any(r["id"] == run_id for r in runs)

        # 5. Retrieve specific run
        run_resp = client.get(f"/api/v1/cases/{case_id}/consistency/runs/{run_id}")
        assert run_resp.status_code == 200
        assert run_resp.json()["id"] == run_id

        # 6. List findings
        findings_resp = client.get(f"/api/v1/cases/{case_id}/consistency/findings")
        assert findings_resp.status_code == 200
        page = findings_resp.json()
        assert "findings" in page
        assert "total" in page
        assert page["limit"] == 50
        assert page["offset"] == 0

        # 7. Check audit ledger records
        audit_events = (
            db_session.query(AuditEventModel)
            .filter(
                AuditEventModel.case_id == case_id,
                AuditEventModel.event_type.in_(
                    [
                        AuditEventType.CONSISTENCY_ANALYSIS_REQUESTED.value,
                        AuditEventType.CONSISTENCY_ANALYSIS_COMPLETED.value,
                    ]
                ),
            )
            .all()
        )
        assert len(audit_events) >= 1

    def test_human_review_workflow_and_history(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify human review actions, status state changes, and append-only audit trail."""
        case_resp = client.post("/api/v1/cases", json={"title": "Review Workflow Case"})
        case_id = case_resp.json()["id"]

        # Seed a consistency finding directly via repository
        repo = ConsistencyRepository(db_session)
        from document_intelligence.domain.identifiers import generate_id
        from document_intelligence.domain.models.consistency import ConsistencyFinding

        finding_id = generate_id()
        finding = ConsistencyFinding(
            id=finding_id,
            case_id=case_id,
            analysis_run_id="run-1",
            rule_id="invoice_receipt_total_consistency",
            title="Invoice Total Mismatch",
            explanation="Invoice total 1000 does not match receipt total 1200.",
            outcome=ConsistencyOutcome.INCONSISTENT,
            status=FindingStatus.DETECTED,
            affected_document_ids=["doc-1", "doc-2"],
        )
        repo.save_finding(finding)
        db_session.commit()

        # Retrieve finding
        get_resp = client.get(f"/api/v1/cases/{case_id}/consistency/findings/{finding_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == finding_id
        assert get_resp.json()["status"] == "DETECTED"
        assert get_resp.json()["is_human_reviewed"] is False

        # 1. Apply CONFIRM_INCONSISTENCY review
        rev_resp1 = client.post(
            f"/api/v1/cases/{case_id}/consistency/findings/{finding_id}/reviews",
            json={
                "decision": ConsistencyReviewAction.CONFIRM_INCONSISTENCY.value,
                "reviewer_id": "investigator-alice",
                "reason": "Confirmed manual inspection shows discrepancy.",
            },
        )
        assert rev_resp1.status_code == 201
        updated = rev_resp1.json()
        assert updated["status"] == FindingStatus.CONFIRMED_OBSERVATION.value
        assert updated["review_status"] == ConsistencyReviewAction.CONFIRM_INCONSISTENCY.value
        assert updated["is_human_reviewed"] is True

        # 2. Apply REQUEST_MORE_EVIDENCE review
        rev_resp2 = client.post(
            f"/api/v1/cases/{case_id}/consistency/findings/{finding_id}/reviews",
            json={
                "decision": ConsistencyReviewAction.REQUEST_MORE_EVIDENCE.value,
                "reviewer_id": "senior-lead-bob",
                "reason": "Requesting purchase order documentation.",
            },
        )
        assert rev_resp2.status_code == 201
        assert rev_resp2.json()["status"] == FindingStatus.NEEDS_REVIEW.value

        # 3. Retrieve review history
        hist_resp = client.get(f"/api/v1/cases/{case_id}/consistency/findings/{finding_id}/reviews")
        assert hist_resp.status_code == 200
        history = hist_resp.json()
        assert len(history) == 2
        assert history[0]["decision"] == ConsistencyReviewAction.CONFIRM_INCONSISTENCY.value
        assert history[0]["reviewer_id"] == "investigator-alice"
        assert history[1]["decision"] == ConsistencyReviewAction.REQUEST_MORE_EVIDENCE.value
        assert history[1]["reviewer_id"] == "senior-lead-bob"

    def test_cross_case_isolation_and_archival_safeguards(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Verify strict case isolation and write protection on archived cases."""
        # Create Case A and Case B
        case_a = client.post("/api/v1/cases", json={"title": "Case A"}).json()["id"]
        case_b = client.post("/api/v1/cases", json={"title": "Case B"}).json()["id"]

        # Seed finding in Case A
        repo = ConsistencyRepository(db_session)
        from document_intelligence.domain.identifiers import generate_id
        from document_intelligence.domain.models.consistency import ConsistencyFinding

        finding_a_id = generate_id()
        finding_a = ConsistencyFinding(
            id=finding_a_id,
            case_id=case_a,
            analysis_run_id="run-A",
            rule_id="invoice_receipt_total_consistency",
            title="Finding in Case A",
            explanation="Discrepancy in Case A",
            outcome=ConsistencyOutcome.INCONSISTENT,
        )
        repo.save_finding(finding_a)
        db_session.commit()

        # Accessing Case A finding from Case B route must return 404
        cross_get = client.get(f"/api/v1/cases/{case_b}/consistency/findings/{finding_a_id}")
        assert cross_get.status_code == 404

        # Reviewing Case A finding through Case B route must return 404
        cross_rev = client.post(
            f"/api/v1/cases/{case_b}/consistency/findings/{finding_a_id}/reviews",
            json={
                "decision": ConsistencyReviewAction.DISMISS.value,
                "reviewer_id": "malicious-user",
                "reason": "Unauthorized review attempt",
            },
        )
        assert cross_rev.status_code == 404

        # Archive Case A
        archive_resp = client.post(f"/api/v1/cases/{case_a}/archive")
        assert archive_resp.status_code == 200

        # Attempting analysis on archived case must return 403 / 422 security error
        analyze_archived = client.post(f"/api/v1/cases/{case_a}/consistency/analyze")
        assert analyze_archived.status_code in (400, 403, 422)

        # Attempting review on archived case must return 403 / 422 security error
        review_archived = client.post(
            f"/api/v1/cases/{case_a}/consistency/findings/{finding_a_id}/reviews",
            json={
                "decision": ConsistencyReviewAction.DISMISS.value,
                "reviewer_id": "rev-1",
                "reason": "Review on archived case",
            },
        )
        assert review_archived.status_code in (400, 403, 422)

    def test_repeated_runs_preserve_historical_findings(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify that executing a new consistency analysis run does not overwrite previous runs."""
        case_resp = client.post("/api/v1/cases", json={"title": "Repeated Runs Case"})
        case_id = case_resp.json()["id"]

        pdf = tmp_path / "doc_1.pdf"
        create_clean_digital_pdf(pdf)
        _upload_pdf(client, case_id, pdf, "doc_1.pdf")

        # Run 1
        run1_resp = client.post(f"/api/v1/cases/{case_id}/consistency/analyze")
        assert run1_resp.status_code == 201
        run1_id = run1_resp.json()["analysis_run_id"]

        # Run 2
        run2_resp = client.post(f"/api/v1/cases/{case_id}/consistency/analyze")
        assert run2_resp.status_code == 201
        run2_id = run2_resp.json()["analysis_run_id"]

        assert run1_id != run2_id

        # Verify both runs are listed
        runs = client.get(f"/api/v1/cases/{case_id}/consistency/runs").json()
        run_ids = [r["id"] for r in runs]
        assert run1_id in run_ids
        assert run2_id in run_ids
