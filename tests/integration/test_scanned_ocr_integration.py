"""Integration tests for scanned document OCR, hybrid routing, and API endpoints."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import PipelineStatus
from tests.fixtures.ocr_factory import (
    create_clean_digital_pdf,
    create_mixed_digital_and_scanned_pdf,
    create_scanned_printed_text_pdf,
)


def _upload_pdf(
    client: TestClient, case_id: str, pdf_path: Path, filename: str = "doc.pdf"
) -> dict[str, Any]:
    with open(pdf_path, "rb") as f:
        resp = client.post(
            f"/api/v1/cases/{case_id}/documents",
            files={"file": (filename, f.read(), "application/pdf")},
        )
    assert resp.status_code == 201
    return resp.json()


class TestScannedOcrIntegration:
    """End-to-end integration tests for optical OCR and hybrid routing via REST API."""

    def test_registered_ocr_analyzers_includes_rapidocr_and_hybrid(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Capabilities Case"})
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "dummy.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/capabilities")
        assert resp.status_code == 200
        engines = resp.json()["registered_ocr_engines"]
        analyzer_ids = [e["analyzer_id"] for e in engines]

        assert "pdfium-ocr-engine" in analyzer_ids
        assert "rapidocr-optical-engine" in analyzer_ids
        assert "hybrid-ocr-pipeline" in analyzer_ids

    def test_scanned_document_hybrid_ocr_execution_and_api_retrieval(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Scanned Invoice Case"})
        case_id = case_resp.json()["id"]

        scan_path = tmp_path / "scanned_voucher.pdf"
        create_scanned_printed_text_pdf(scan_path)
        doc = _upload_pdf(client, case_id, scan_path, "scanned_voucher.pdf")
        doc_id = doc["id"]

        # Trigger hybrid OCR
        ocr_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "hybrid-ocr-pipeline"},
        )
        assert ocr_resp.status_code == 201
        res = ocr_resp.json()
        assert res["processing_run"]["status"] == PipelineStatus.SUCCEEDED.value

        # Retrieve text
        text_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text")
        assert text_resp.status_code == 200
        text_data = text_resp.json()

        assert text_data["total_pages"] == 1
        page = text_data["pages"][0]
        assert page["engine_name"] == "rapidocr-onnxruntime"
        assert page["routing_decision"] in ("IMAGE_ONLY_SCANNED_PAGE", "OCR_ONLY")
        assert len(page["tokens"]) > 5

        # Verify no host filesystem paths leaked
        resp_text = text_resp.text
        assert "C:\\" not in resp_text
        assert "D:\\" not in resp_text

    def test_mixed_document_ocr_api_page_filtering_and_provenance(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Mixed OCR Case"})
        case_id = case_resp.json()["id"]

        mixed_path = tmp_path / "mixed_sample.pdf"
        create_mixed_digital_and_scanned_pdf(mixed_path)
        doc_id = _upload_pdf(client, case_id, mixed_path)["id"]

        ocr_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "hybrid-ocr-pipeline"},
        )
        assert ocr_resp.status_code == 201

        # Query Page 1 only (Digital PDFium)
        p1_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text?page_number=1")
        assert p1_resp.status_code == 200
        p1_data = p1_resp.json()
        assert p1_data["total_pages"] == 1
        assert p1_data["pages"][0]["engine_name"] == "pypdfium2"
        assert p1_data["pages"][0]["routing_decision"] in ("DIGITAL_VECTOR_PRIMARY", "VECTOR_ONLY")

        # Query Page 2 only (Scanned RapidOCR)
        p2_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text?page_number=2")
        assert p2_resp.status_code == 200
        p2_data = p2_resp.json()
        assert p2_data["total_pages"] == 1
        assert p2_data["pages"][0]["engine_name"] == "rapidocr-onnxruntime"
        assert p2_data["pages"][0]["routing_decision"] in ("IMAGE_ONLY_SCANNED_PAGE", "OCR_ONLY")

        # Filter by engine_name
        engine_filter_resp = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text?engine_name=rapidocr"
        )
        assert engine_filter_resp.status_code == 200
        ef_data = engine_filter_resp.json()
        assert ef_data["total_pages"] == 1
        assert ef_data["pages"][0]["page_number"] == 2

    def test_token_retrieval_and_filtering_on_scanned_document(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Token Search Case"})
        case_id = case_resp.json()["id"]

        scan_path = tmp_path / "scanned_doc.pdf"
        create_scanned_printed_text_pdf(scan_path)
        doc_id = _upload_pdf(client, case_id, scan_path)["id"]

        client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr")

        # Query tokens with query string
        tokens_resp = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/tokens?query=statement"
        )
        assert tokens_resp.status_code == 200
        tokens_data = tokens_resp.json()
        assert tokens_data["total_count"] >= 1
        token = tokens_data["tokens"][0]
        assert "STATEMENT" in token["raw_text"].upper()
        assert token["bounding_box"] is not None
        assert 0.0 <= token["bounding_box"]["x"] <= 1.0
        assert 0.0 <= token["bounding_box"]["y"] <= 1.0

    def test_direct_rapidocr_analyzer_execution(self, client: TestClient, tmp_path: Path) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Direct RapidOCR Case"})
        case_id = case_resp.json()["id"]

        scan_path = tmp_path / "scanned_direct.pdf"
        create_scanned_printed_text_pdf(scan_path)
        doc_id = _upload_pdf(client, case_id, scan_path)["id"]

        ocr_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "rapidocr-optical-engine"},
        )
        assert ocr_resp.status_code == 201
        run = ocr_resp.json()["processing_run"]
        assert "rapidocr" in run["pipeline_name"].lower()
