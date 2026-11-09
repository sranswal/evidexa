"""Integration tests for Document Classification and Structured Field Extraction APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    AuditEventType,
    DocumentClass,
    EvidenceType,
)
from document_intelligence.infrastructure.persistence.models import (
    AuditEventModel,
    EvidenceNodeModel,
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


class TestUnderstandingApiIntegration:
    """End-to-end integration tests for document classification and structured extraction."""

    def test_document_classification_workflow(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        # 1. Create case & upload invoice PDF
        case_resp = client.post("/api/v1/cases", json={"title": "Classification Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        # 2. Run OCR first
        ocr_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "pdfium-ocr-engine"},
        )
        assert ocr_resp.status_code == 201

        # 3. Classify document via API
        class_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/classification",
            json={},
        )
        assert class_resp.status_code == 200
        class_res = class_resp.json()

        assert class_res["document_id"] == doc_id
        assert class_res["predicted_class"] == DocumentClass.INVOICE.value
        assert class_res["effective_class"] == DocumentClass.INVOICE.value
        assert class_res["ranking_score"] > 0.3
        assert class_res["score_type"] == "rule_ranking_score"
        assert len(class_res["candidates"]) > 0
        assert len(class_res["page_classifications"]) == 1
        assert class_res["page_classifications"][0]["page_number"] == 1

        # 4. GET classification
        get_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/classification")
        assert get_resp.status_code == 200
        get_res = get_resp.json()
        assert get_res["predicted_class"] == DocumentClass.INVOICE.value

        # 5. Check audit event
        audit = (
            db_session.query(AuditEventModel)
            .filter_by(
                case_id=case_id,
                event_type=AuditEventType.DOCUMENT_CLASSIFIED.value,
            )
            .first()
        )
        assert audit is not None
        assert audit.payload["predicted_class"] == DocumentClass.INVOICE.value

    def test_classification_human_override(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Override Case"})
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        # Run OCR & Classify
        client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "pdfium-ocr-engine"},
        )
        client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/classification")

        # Human override
        override_payload = {
            "target_class": DocumentClass.CONTRACT.value,
            "reason": "Document includes master agreement signature addendum.",
            "overridden_by": "lead-investigator-01",
        }
        override_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/classification/override",
            json=override_payload,
        )
        assert override_resp.status_code == 200
        ov_res = override_resp.json()

        assert (
            ov_res["predicted_class"] == DocumentClass.INVOICE.value
        )  # Original machine prediction preserved
        assert ov_res["effective_class"] == DocumentClass.CONTRACT.value  # Effective class changed
        assert ov_res["manual_override"] is not None
        assert ov_res["manual_override"]["original_class"] == DocumentClass.INVOICE.value
        assert ov_res["manual_override"]["overridden_class"] == DocumentClass.CONTRACT.value
        assert ov_res["manual_override"]["overridden_by"] == "lead-investigator-01"

        # Check audit ledger
        ov_audit = (
            db_session.query(AuditEventModel)
            .filter_by(
                case_id=case_id,
                event_type=AuditEventType.DOCUMENT_CLASSIFICATION_OVERRIDDEN.value,
            )
            .first()
        )
        assert ov_audit is not None
        assert ov_audit.payload["overridden_class"] == DocumentClass.CONTRACT.value
        assert ov_audit.payload["original_class"] == DocumentClass.INVOICE.value

    def test_structured_field_extraction_and_evidence_graph(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Extraction Case"})
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        # Run OCR
        client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "pdfium-ocr-engine"},
        )

        # 1. Test schema discovery endpoints
        schemas_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction/schemas")
        assert schemas_resp.status_code == 200
        schema_list = schemas_resp.json()
        assert len(schema_list) >= 3
        schema_ids = {s["schema_id"] for s in schema_list}
        assert "invoice_v1" in schema_ids
        assert "receipt_v1" in schema_ids
        assert "bank_statement_v1" in schema_ids

        # Test single schema GET
        inv_schema_resp = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction/schemas/invoice_v1"
        )
        assert inv_schema_resp.status_code == 200
        assert inv_schema_resp.json()["schema_id"] == "invoice_v1"

        # 2. Extract structured fields with explicit schema
        ext_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert ext_resp.status_code == 200
        ext_res = ext_resp.json()

        assert ext_res["document_id"] == doc_id
        assert ext_res["schema_id"] == "invoice_v1"
        assert len(ext_res["fields"]) > 0

        # Check extracted fields
        fields = ext_res["fields"]
        assert "invoice_number" in fields
        assert "INV-2026-8801" in fields["invoice_number"]["raw_text"]
        assert fields["invoice_number"]["source_page_number"] == 1

        # Check date normalization
        assert "invoice_date" in fields
        assert fields["invoice_date"]["normalized_value"] == "2026-11-09"

        # 3. Check Evidence Graph persistence in database
        field_evidence_nodes = (
            db_session.query(EvidenceNodeModel)
            .filter_by(
                case_id=case_id,
                document_id=doc_id,
                evidence_type=EvidenceType.EXTRACTED_FIELD.value,
            )
            .all()
        )
        assert len(field_evidence_nodes) >= len(fields)
        for ev in field_evidence_nodes:
            assert ev.source_component == "structured-field-extractor"
            assert ev.normalized_value is not None or ev.raw_value is not None

        # 4. Check audit event
        audit = (
            db_session.query(AuditEventModel)
            .filter_by(
                case_id=case_id,
                event_type=AuditEventType.FIELDS_EXTRACTED.value,
            )
            .first()
        )
        assert audit is not None
        assert audit.payload["schema_id"] == "invoice_v1"

        # 5. GET latest extraction
        get_ext = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction")
        assert get_ext.status_code == 200
        assert get_ext.json()["schema_id"] == "invoice_v1"

    def test_archived_case_prohibits_understanding_operations(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Archived Case"})
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        # Run OCR while open
        client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "pdfium-ocr-engine"},
        )

        # Archive case
        archive_resp = client.post(f"/api/v1/cases/{case_id}/archive")
        assert archive_resp.status_code == 200

        # Attempt classification -> rejected
        class_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/classification")
        assert class_resp.status_code in (400, 422)

        # Attempt override -> rejected
        ov_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/classification/override",
            json={
                "target_class": DocumentClass.RECEIPT.value,
                "reason": "Test reason",
                "overridden_by": "user-1",
            },
        )
        assert ov_resp.status_code in (400, 422)

        # Attempt extraction -> rejected
        ext_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert ext_resp.status_code in (400, 422)

    def test_cross_case_isolation(self, client: TestClient, tmp_path: Path) -> None:
        case1 = client.post("/api/v1/cases", json={"title": "Case 1"}).json()["id"]
        case2 = client.post("/api/v1/cases", json={"title": "Case 2"}).json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case1, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        # Attempt accessing doc from case 2
        resp = client.get(f"/api/v1/cases/{case2}/documents/{doc_id}/classification")
        assert resp.status_code == 404
