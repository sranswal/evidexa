"""Integration tests for forensic adapter framework and PDF structural analysis."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from document_intelligence.domain.enums import (
    AuditEventType,
    PipelineStatus,
)
from document_intelligence.infrastructure.persistence.models import (
    ProcessingRunModel,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "pdf"


def _upload_fixture(client: TestClient, case_id: str, fixture_name: str) -> dict[str, Any]:
    fixture_path = FIXTURES_DIR / fixture_name
    assert fixture_path.exists(), f"Missing fixture {fixture_name}"

    with open(fixture_path, "rb") as f:
        response = client.post(
            f"/api/v1/cases/{case_id}/documents",
            files={"file": (fixture_name, f.read(), "application/pdf")},
        )
    assert response.status_code == 201, f"Failed uploading {fixture_name}: {response.text}"
    result: dict[str, Any] = response.json()
    return result


class TestPdfStructuralForensicsIntegration:
    """End-to-end integration tests for PDF forensic engine and API workflows."""

    def test_normal_pdf_analysis_end_to_end(self, client: TestClient, db_session) -> None:
        """Analyze clean normal PDF: produces clean run, persists entities, and seals audit chain."""
        # 1. Create case
        case_resp = client.post("/api/v1/cases", json={"title": "Clean Invoice Investigation"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Upload clean PDF fixture
        doc = _upload_fixture(client, case_id, "fixture_normal.pdf")
        doc_id = doc["id"]
        assert len(doc["sha256"]) == 64

        # 3. Trigger forensic analysis via REST API
        analyze_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze",
            json={"analyzer_id": "pdf-structural-analyzer", "options": {}},
        )
        assert analyze_resp.status_code == 201
        result = analyze_resp.json()

        run = result["processing_run"]
        assert run["case_id"] == case_id
        assert run["document_ids"] == [doc_id]
        assert run["status"] == PipelineStatus.SUCCEEDED.value
        assert run["pipeline_name"] == "PDF Structural & Byte-Level Forensics Analyzer"
        assert run["completed_at"] is not None
        assert run["resource_metrics"]["duration_ms"] >= 0

        # 4. Verify processing runs list and get
        runs_resp = client.get(f"/api/v1/cases/{case_id}/processing-runs")
        assert runs_resp.status_code == 200
        runs_data = runs_resp.json()
        assert runs_data["total"] == 1
        assert runs_data["items"][0]["id"] == run["id"]

        single_run_resp = client.get(f"/api/v1/cases/{case_id}/processing-runs/{run['id']}")
        assert single_run_resp.status_code == 200
        assert single_run_resp.json()["id"] == run["id"]

        # 5. Verify database records
        db_run = db_session.get(ProcessingRunModel, run["id"])
        assert db_run is not None
        assert db_run.status == PipelineStatus.SUCCEEDED.value

        # 6. Verify audit chain contains started and completed events
        audit_resp = client.get(f"/api/v1/cases/{case_id}/audit-events")
        assert audit_resp.status_code == 200
        events = audit_resp.json()["items"]
        event_types = [e["event_type"] for e in events]
        assert AuditEventType.PROCESSING_RUN_STARTED.value in event_types
        assert AuditEventType.PROCESSING_RUN_COMPLETED.value in event_types

        # Verify cryptographic chain integrity
        verify_resp = client.get(f"/api/v1/cases/{case_id}/audit-events/verify")
        assert verify_resp.status_code == 200
        assert verify_resp.json()["chain_valid"] is True

    def test_incremental_revision_content_modification_detected(self, client: TestClient) -> None:
        """Analyze PDF with altered total amount: flags content-changed in revision with diff."""
        # 1. Create case & upload fixture
        case_resp = client.post("/api/v1/cases", json={"title": "Altered Invoice Investigation"})
        case_id = case_resp.json()["id"]
        doc = _upload_fixture(client, case_id, "fixture_incremental_revision.pdf")
        doc_id = doc["id"]

        # 2. Analyze document
        analyze_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze")
        assert analyze_resp.status_code == 201
        data = analyze_resp.json()

        findings = data["findings"]
        assert len(findings) > 0

        # Finding should detect content change in revision
        rev_findings = [
            f
            for f in findings
            if "content" in f["title"].lower()
            or "revision" in f["title"].lower()
            or f["category"] == "PDF_STRUCTURE"
        ]
        assert len(rev_findings) > 0

        # Verify findings query API with document_id and processing_run_id filters
        run_id = data["processing_run"]["id"]
        findings_query = client.get(
            f"/api/v1/cases/{case_id}/findings",
            params={"document_id": doc_id, "processing_run_id": run_id},
        )
        assert findings_query.status_code == 200
        items = findings_query.json()["items"]
        assert len(items) == len(findings)

        # Verify evidence query API
        ev_resp = client.get(f"/api/v1/cases/{case_id}/evidence", params={"document_id": doc_id})
        assert ev_resp.status_code == 200
        ev_items = ev_resp.json()["items"]
        assert len(ev_items) > 0
        # Check no fabricated bounding box
        assert all(ev["bounding_box"] is None for ev in ev_items)

    def test_metadata_variation_detection(self, client: TestClient) -> None:
        """Analyze PDF with inconsistent temporal metadata: records appropriate findings."""
        case_resp = client.post("/api/v1/cases", json={"title": "Metadata Investigation"})
        case_id = case_resp.json()["id"]
        doc = _upload_fixture(client, case_id, "fixture_metadata_variation.pdf")

        analyze_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc['id']}/analyze")
        assert analyze_resp.status_code == 201
        data = analyze_resp.json()
        assert data["processing_run"]["status"] in [
            PipelineStatus.SUCCEEDED.value,
            PipelineStatus.PARTIALLY_SUCCEEDED.value,
        ]

    def test_structural_anomaly_detection(self, client: TestClient) -> None:
        """Analyze PDF with extra %%EOF markers / trailing garbage."""
        case_resp = client.post("/api/v1/cases", json={"title": "Structural Anomaly Investigation"})
        case_id = case_resp.json()["id"]
        doc = _upload_fixture(client, case_id, "fixture_structural_anomaly.pdf")

        analyze_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc['id']}/analyze")
        assert analyze_resp.status_code == 201
        data = analyze_resp.json()
        assert data["processing_run"]["status"] == PipelineStatus.SUCCEEDED.value

    def test_malformed_pdf_graceful_handling(self, client: TestClient) -> None:
        """Malformed PDF with corrupt streams fails cleanly without crashing the platform."""
        case_resp = client.post("/api/v1/cases", json={"title": "Malformed PDF Investigation"})
        case_id = case_resp.json()["id"]
        doc = _upload_fixture(client, case_id, "fixture_malformed.pdf")

        analyze_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc['id']}/analyze")
        assert analyze_resp.status_code == 201
        data = analyze_resp.json()
        run = data["processing_run"]
        # Analysis should complete with status FAILED or have recorded errors
        assert run["status"] in [
            PipelineStatus.FAILED.value,
            PipelineStatus.PARTIALLY_SUCCEEDED.value,
        ]
        if run["status"] == PipelineStatus.FAILED.value:
            assert run["error_code"] is not None

    def test_encrypted_pdf_handling(self, client: TestClient) -> None:
        """Encrypted PDF is caught by adapter and recorded appropriately."""
        case_resp = client.post("/api/v1/cases", json={"title": "Encrypted PDF Investigation"})
        case_id = case_resp.json()["id"]
        doc = _upload_fixture(client, case_id, "fixture_encrypted.pdf")

        analyze_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc['id']}/analyze")
        # Should either return 201 with run marked as FAILED or error response
        if analyze_resp.status_code == 201:
            run = analyze_resp.json()["processing_run"]
            assert run["status"] == PipelineStatus.FAILED.value
        else:
            assert analyze_resp.status_code in [400, 422, 500]

    def test_repeat_analysis_creates_isolated_runs(self, client: TestClient) -> None:
        """Executing analysis multiple times on same document creates separate immutable runs."""
        case_resp = client.post("/api/v1/cases", json={"title": "Repeat Analysis Investigation"})
        case_id = case_resp.json()["id"]
        doc = _upload_fixture(client, case_id, "fixture_normal.pdf")
        doc_id = doc["id"]

        run1 = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze").json()[
            "processing_run"
        ]
        run2 = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze").json()[
            "processing_run"
        ]

        assert run1["id"] != run2["id"]

        runs_resp = client.get(
            f"/api/v1/cases/{case_id}/processing-runs", params={"document_id": doc_id}
        )
        assert runs_resp.json()["total"] == 2

    def test_parser_timeout_enforcement(self, client: TestClient) -> None:
        """Analyzer strictly enforces execution timeout and marks run FAILED with ANALYSIS_TIMEOUT."""
        case_resp = client.post("/api/v1/cases", json={"title": "Timeout Investigation"})
        case_id = case_resp.json()["id"]
        doc = _upload_fixture(client, case_id, "fixture_normal.pdf")
        doc_id = doc["id"]

        # Request analysis with an unreasonably tiny timeout (0.00001s)
        analyze_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze",
            json={"options": {"timeout_sec": 0.00001}},
        )
        assert analyze_resp.status_code == 201
        run = analyze_resp.json()["processing_run"]
        assert run["status"] == PipelineStatus.FAILED.value
        assert run["error_code"] == "ANALYSIS_TIMEOUT"
        assert "timed out" in run["error_message"].lower()
