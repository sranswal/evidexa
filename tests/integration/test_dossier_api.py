"""Integration tests for Investigation Dossier and Aggregated Findings API."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pikepdf
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.infrastructure.repositories.finding_repository import (
    FindingRepository,
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


class TestDossierApiIntegration:
    """Validate REST API endpoints for Findings Aggregation, Dossier Generation, and Export."""

    def test_dossier_api_end_to_end_workflow(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        # 1. Create case
        case_resp = client.post("/api/v1/cases", json={"title": "Dossier Full Workflow Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Upload document
        pdf_path = create_clean_digital_pdf(tmp_path / "test_invoice.pdf")
        doc_resp = _upload_pdf(client, case_id, pdf_path, "test_invoice.pdf")
        doc_id = doc_resp["id"]

        # 3. Seed a forensic finding directly
        finding_repo = FindingRepository(db_session)
        ff = ForensicFinding(
            id="ff-int-001",
            case_id=case_id,
            processing_run_id="run-int-1",
            document_id=doc_id,
            category=FindingCategory.PDF_STRUCTURE,
            severity=FindingSeverity.HIGH,
            status=FindingStatus.DETECTED,
            title="Modified object catalog detected",
            description="Catalog dictionary references unregistered objects",
            confidence=0.92,
            source_component="pdf_structural_forensics",
            evidence_ids=["ev-test-1"],
        )
        finding_repo.save(ff)

        # 4. GET /cases/{case_id}/findings/aggregated
        agg_resp = client.get(f"/api/v1/cases/{case_id}/findings/aggregated")
        assert agg_resp.status_code == 200
        aggregated = agg_resp.json()
        assert len(aggregated) == 1
        finding_item = aggregated[0]
        assert finding_item["id"] == "ff-int-001"
        assert finding_item["category"] == "STRUCTURAL_ANOMALY"
        assert finding_item["is_reviewed"] is False

        # 5. POST /cases/{case_id}/findings/aggregated/{finding_id}/reviews
        review_payload = {
            "reviewer_id": "senior-examiner",
            "action": "CONFIRM_OBSERVATION",
            "rationale": "Verified object stream trailer manually.",
        }
        rev_resp = client.post(
            f"/api/v1/cases/{case_id}/findings/aggregated/ff-int-001/reviews",
            json=review_payload,
        )
        assert rev_resp.status_code == 201
        review_data = rev_resp.json()
        assert review_data["finding_id"] == "ff-int-001"
        assert review_data["reviewer_id"] == "senior-examiner"
        assert review_data["new_status"] == "CONFIRM_OBSERVATION"

        # 6. GET reviews history
        rev_list_resp = client.get(
            f"/api/v1/cases/{case_id}/findings/aggregated/ff-int-001/reviews"
        )
        assert rev_list_resp.status_code == 200
        assert len(rev_list_resp.json()) == 1

        # 7. POST /cases/{case_id}/dossiers/generate
        gen_resp = client.post(
            f"/api/v1/cases/{case_id}/dossiers/generate",
            json={
                "created_by": "senior-examiner",
                "scope_and_purpose": "Cross-border forensic inquiry",
            },
        )
        assert gen_resp.status_code == 201
        dossier = gen_resp.json()
        dossier_id = dossier["id"]
        assert dossier["version"] == 1
        assert dossier["status"] == "DRAFT"
        assert len(dossier["sections"]) == 12

        # 8. GET /cases/{case_id}/dossiers
        list_resp = client.get(f"/api/v1/cases/{case_id}/dossiers")
        assert list_resp.status_code == 200
        dossiers_list = list_resp.json()
        assert len(dossiers_list) == 1
        assert dossiers_list[0]["id"] == dossier_id

        # 9. GET /cases/{case_id}/dossiers/{dossier_id}
        get_resp = client.get(f"/api/v1/cases/{case_id}/dossiers/{dossier_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == dossier_id

        # 10. POST /cases/{case_id}/dossiers/{dossier_id}/finalize
        fin_resp = client.post(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/finalize",
            json={"user_id": "lead-supervisor"},
        )
        assert fin_resp.status_code == 200
        finalized = fin_resp.json()
        assert finalized["status"] == "APPROVED"
        assert finalized["content_hash"] is not None
        assert len(finalized["content_hash"]) == 64

        # 11. GET /cases/{case_id}/dossiers/{dossier_id}/export?format=pdf
        export_pdf_resp = client.get(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/export?format=pdf"
        )
        assert export_pdf_resp.status_code == 200
        assert export_pdf_resp.headers["content-type"] == "application/pdf"
        assert "Content-Disposition" in export_pdf_resp.headers
        # Verify valid PDF with pikepdf
        with pikepdf.open(io.BytesIO(export_pdf_resp.content)) as p:
            assert len(p.pages) >= 1

        # 12. GET /cases/{case_id}/dossiers/{dossier_id}/export?format=json
        export_json_resp = client.get(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/export?format=json"
        )
        assert export_json_resp.status_code == 200
        assert "application/json" in export_json_resp.headers["content-type"]
        json_body = export_json_resp.json()
        assert json_body["dossier_id"] == dossier_id
        assert "legal_disclaimer" in json_body
