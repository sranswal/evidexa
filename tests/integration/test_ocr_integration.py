"""Integration tests for OCR and Document Understanding API endpoints, Evidence Graph, and audit sealing."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    AuditEventType,
    EvidenceType,
    PipelineStatus,
)
from document_intelligence.infrastructure.persistence.models import (
    AuditEventModel,
    EvidenceNodeModel,
)
from tests.fixtures.ocr_factory import (
    create_clean_digital_pdf,
    create_multi_column_pdf,
    create_table_pdf,
)


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


class TestOcrIntegration:
    """End-to-end integration tests for OCR and Document Understanding."""

    def test_ocr_engine_discovered_in_analyzers_list(self, client: TestClient) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "OCR Discovery Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        resp = client.get(f"/api/v1/cases/{case_id}/analyzers")
        assert resp.status_code == 200
        analyzers = resp.json()
        analyzer_ids = {a["analyzer_id"] for a in analyzers}

        assert "pdfium-ocr-engine" in analyzer_ids

    def test_clean_digital_pdf_ocr_execution_and_text_retrieval(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        # 1. Create case & upload PDF
        case_resp = client.post("/api/v1/cases", json={"title": "OCR Invoice Case"})
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        # 2. Trigger OCR via dedicated endpoint
        ocr_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "pdfium-ocr-engine"},
        )
        assert ocr_resp.status_code == 201
        ocr_res = ocr_resp.json()
        run = ocr_res["processing_run"]
        assert run["status"] == PipelineStatus.SUCCEEDED.value
        assert "ocr" in run["pipeline_name"].lower()

        # 3. Retrieve extracted text
        text_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text")
        assert text_resp.status_code == 200
        doc_text = text_resp.json()
        assert doc_text["total_pages"] == 1
        assert doc_text["total_tokens"] > 30
        assert "ACME AUDIT" in doc_text["full_raw_text"]
        assert doc_text["pages"][0]["has_vector_text"] is True

        # 4. Retrieve tokens with search query
        token_resp = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/tokens?query=INV-2026-8801"
        )
        assert token_resp.status_code == 200
        token_data = token_resp.json()
        assert token_data["total_count"] >= 1
        matched_token = token_data["tokens"][0]
        assert "INV-2026-8801" in matched_token["raw_text"]
        assert matched_token["bounding_box"] is not None

        # 5. Check EvidenceNode records in DB
        nodes = (
            db_session.query(EvidenceNodeModel)
            .filter_by(case_id=case_id, processing_run_id=run["id"])
            .all()
        )
        assert len(nodes) >= 1
        types = {n.evidence_type for n in nodes}
        assert EvidenceType.OCR_TEXT.value in types

        # 6. Check Audit trail
        audits = (
            db_session.query(AuditEventModel)
            .filter_by(case_id=case_id)
            .order_by(AuditEventModel.sequence_number)
            .all()
        )
        audit_types = [a.event_type for a in audits]
        assert AuditEventType.ANALYSIS_REQUESTED.value in audit_types
        assert AuditEventType.PROCESSING_RUN_STARTED.value in audit_types
        assert AuditEventType.PROCESSING_RUN_COMPLETED.value in audit_types

    def test_table_extraction_endpoint(self, client: TestClient, tmp_path: Path) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "OCR Table Case"})
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "table.pdf"
        create_table_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "disbursements.pdf")
        doc_id = doc["id"]

        # Run OCR
        ocr_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr")
        assert ocr_resp.status_code == 201

        # Query tables endpoint
        tbl_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/tables")
        assert tbl_resp.status_code == 200
        tables = tbl_resp.json()
        assert len(tables) >= 1
        tbl = tables[0]
        assert tbl["num_rows"] >= 4
        assert tbl["num_cols"] >= 3
        assert len(tbl["cells"]) >= 12

    def test_layout_regions_endpoint(self, client: TestClient, tmp_path: Path) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "OCR Layout Case"})
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "multi_col.pdf"
        create_multi_column_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "report.pdf")
        doc_id = doc["id"]

        # Run OCR
        ocr_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr")
        assert ocr_resp.status_code == 201

        # Query layout endpoint
        layout_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/layout")
        assert layout_resp.status_code == 200
        regions = layout_resp.json()
        assert len(regions) >= 1
        region_types = {r["region_type"] for r in regions}
        assert "HEADER" in region_types or "PARAGRAPH" in region_types

    def test_cross_case_ocr_access_rejected(self, client: TestClient, tmp_path: Path) -> None:
        # Case A & Document A
        case_a = client.post("/api/v1/cases", json={"title": "Case A"}).json()["id"]
        pdf_path = tmp_path / "doc.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_a = _upload_pdf(client, case_a, pdf_path)["id"]

        # Case B
        case_b = client.post("/api/v1/cases", json={"title": "Case B"}).json()["id"]

        # Case B cannot trigger OCR on Document A
        resp = client.post(f"/api/v1/cases/{case_b}/documents/{doc_a}/ocr")
        assert resp.status_code in (400, 404, 422)

    def test_archived_case_prohibits_ocr_initiation(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Archived Case Check"})
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "doc.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        # Transition case to ARCHIVED
        archive_resp = client.post(f"/api/v1/cases/{case_id}/archive")
        assert archive_resp.status_code == 200

        # OCR initiation must fail
        resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr")
        assert resp.status_code in [400, 422]
        assert "archived" in resp.text.lower()
