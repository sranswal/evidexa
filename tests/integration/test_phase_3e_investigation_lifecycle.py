"""EVIDEXA Phase 3E: Full Investigation Lifecycle Integration & Reliability Test.

Validates the complete 10-step investigator workflow end-to-end:
1. Create a case.
2. Upload multiple original documents (Invoice, Receipt, Bank Statement).
3. Process documents through forensic, OCR, classification, and consistency analyzers.
4. Inspect OCR, extracted fields, and forensic findings.
5. Explore cross-document relationships and paths in the unified Evidence Graph.
6. Review aggregated case findings.
7. Record append-only human review determinations with rationale.
8. Generate an investigation dossier with 12 canonical sections.
9. Finalize and freeze the dossier with an immutable canonical SHA-256 hash.
10. Export vector PDF and structured JSON reports, verifying cryptographic content hash equality.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pikepdf
from fastapi.testclient import TestClient
from pikepdf import Array, Dictionary, Name
from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    CaseStatus,
    DossierStatus,
)
from document_intelligence.modules.dossier.generator import compute_canonical_content_hash


def _create_synthetic_invoice_pdf(path: Path) -> Path:
    """Create a clean digital invoice PDF with extractable vector text."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    stream_content = (
        b"BT /F2 18 Tf 50 720 Td (INVOICE - APEX TECHNICAL CONSULTING) Tj ET\n"
        b"BT /F1 12 Tf 50 690 Td (Invoice Number: INV-2026-9001) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (Invoice Date: November 10, 2026) Tj ET\n"
        b"BT /F1 12 Tf 50 650 Td (Vendor: Apex Technical Consulting Ltd) Tj ET\n"
        b"BT /F1 12 Tf 50 630 Td (Buyer: Global DataOps Corporation) Tj ET\n"
        b"BT /F1 12 Tf 50 600 Td (Description: Enterprise Forensic Audit Services) Tj ET\n"
        b"BT /F2 14 Tf 50 560 Td (Total Amount: $12,500.00 USD) Tj ET\n"
        b"BT /F1 10 Tf 50 520 Td (Payment Terms: Net 30 days) Tj ET\n"
    )

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _create_synthetic_scanned_receipt_pdf(path: Path) -> Path:
    """Create a scanned image-based receipt PDF with intentional price discrepancy ($11,000.00 vs $12,500.00)."""
    w, h = 800, 1050
    img = Image.new("RGB", (w, h), color=(248, 246, 240))
    draw = ImageDraw.Draw(img)

    draw.text((60, 60), "OFFICIAL PAYMENT RECEIPT", fill=(20, 20, 20))
    draw.text((60, 110), "Receipt Number: REC-2026-9001", fill=(40, 40, 40))
    draw.text((60, 140), "Reference Invoice: INV-2026-9001", fill=(40, 40, 40))
    draw.text((60, 170), "Merchant: Apex Technical Consulting Ltd", fill=(40, 40, 40))
    draw.text((60, 200), "Date: November 12, 2026", fill=(40, 40, 40))
    draw.text((60, 250), "Amount Received: $11,000.00 USD", fill=(10, 10, 10))
    draw.text((60, 290), "Payment Method: Wire Transfer", fill=(40, 40, 40))

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG", quality=90)
    img_bytes = img_byte_arr.getvalue()

    pdf = pikepdf.new()
    image_obj = pdf.make_stream(img_bytes)
    image_obj.Type = Name.XObject
    image_obj.Subtype = Name.Image
    image_obj.Width = w
    image_obj.Height = h
    image_obj.ColorSpace = Name.DeviceRGB
    image_obj.BitsPerComponent = 8
    image_obj.Filter = Name.DCTDecode

    resources = Dictionary(XObject=Dictionary(Im1=image_obj))
    stream_content = f"q {w * 0.75} 0 0 {h * 0.75} 0 0 cm /Im1 Do Q\n".encode()

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, w * 0.75, h * 0.75]),
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _create_synthetic_bank_statement_pdf(path: Path) -> Path:
    """Create a digital bank statement PDF with corresponding transaction records."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    font_bold = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold)
    )
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    stream_content = (
        b"BT /F2 18 Tf 50 720 Td (FIRST METROPOLITAN COMMERCIAL BANK) Tj ET\n"
        b"BT /F1 12 Tf 50 690 Td (Account Number: ACC-9941-02) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (Statement Period: November 2026) Tj ET\n"
        b"BT /F1 12 Tf 50 650 Td (Account Holder: Global DataOps Corporation) Tj ET\n"
        b"BT /F2 12 Tf 50 610 Td (DATE        DESCRIPTION                           AMOUNT) Tj ET\n"
        b"BT /F1 11 Tf 50 580 Td (2026-11-12  WIRE OUT - APEX TECH CONSULTING      -$11,000.00) Tj ET\n"
        b"BT /F1 11 Tf 50 550 Td (Ending Balance: $148,500.00 USD) Tj ET\n"
    )

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path


def _upload_pdf(client: TestClient, case_id: str, pdf_path: Path, filename: str) -> dict[str, Any]:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, f"Failed uploading PDF {filename}: {response.text}"
    return response.json()


class TestPhase3EInvestigationLifecycle:
    """Full End-to-End Investigation Lifecycle, Cross-Workspace Integration & Reliability Suite."""

    def test_complete_investigation_lifecycle_workflow(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        # =====================================================================
        # Step A: Case & Ingestion
        # =====================================================================
        # 1. Create a primary investigation case
        case_resp = client.post(
            "/api/v1/cases",
            json={
                "title": "Operation Sovereign Delta",
                "description": "Multi-document corporate audit and forensic verification scenario",
                "created_by": "lead-investigator",
            },
        )
        assert case_resp.status_code == 201
        case_data = case_resp.json()
        case_id = case_data["id"]
        assert case_data["status"] == CaseStatus.DRAFT.value
        assert case_data["case_reference"].startswith("CASE-")

        # 2. Generate synthetic deterministic document fixtures
        invoice_path = _create_synthetic_invoice_pdf(tmp_path / "invoice_9001.pdf")
        receipt_path = _create_synthetic_scanned_receipt_pdf(tmp_path / "receipt_9001.pdf")
        statement_path = _create_synthetic_bank_statement_pdf(tmp_path / "bank_statement.pdf")

        with open(invoice_path, "rb") as f:
            invoice_bytes = f.read()
        expected_invoice_hash = hashlib.sha256(invoice_bytes).hexdigest()

        # 3. Upload documents
        inv_doc = _upload_pdf(client, case_id, invoice_path, "invoice_9001.pdf")
        rec_doc = _upload_pdf(client, case_id, receipt_path, "receipt_9001.pdf")
        stmt_doc = _upload_pdf(client, case_id, statement_path, "bank_statement.pdf")

        inv_id = inv_doc["id"]
        rec_id = rec_doc["id"]
        stmt_id = stmt_doc["id"]
        assert stmt_id is not None

        # 4. Verify document SHA-256 integrity
        assert inv_doc["sha256"] == expected_invoice_hash
        assert len(rec_doc["sha256"]) == 64
        assert len(stmt_doc["sha256"]) == 64

        # 5. Verify duplicate detection (uploading identical file again)
        dup_resp = client.post(
            f"/api/v1/cases/{case_id}/documents",
            files={"file": ("invoice_9001_copy.pdf", invoice_bytes, "application/pdf")},
        )
        assert dup_resp.status_code == 201
        dup_data = dup_resp.json()
        assert dup_data["sha256"] == expected_invoice_hash

        # 6. Verify original document download
        dl_resp = client.get(f"/api/v1/cases/{case_id}/documents/{inv_id}/download")
        assert dl_resp.status_code == 200
        assert dl_resp.headers["content-type"] == "application/pdf"
        assert dl_resp.content == invoice_bytes

        # 7. Verify archived-case upload restrictions
        archive_case_resp = client.post("/api/v1/cases", json={"title": "Archived Test Case"})
        archive_case_id = archive_case_resp.json()["id"]
        client.post(f"/api/v1/cases/{archive_case_id}/archive")

        arch_upload_resp = client.post(
            f"/api/v1/cases/{archive_case_id}/documents",
            files={"file": ("test.pdf", invoice_bytes, "application/pdf")},
        )
        assert arch_upload_resp.status_code in (400, 422)
        assert "archived" in arch_upload_resp.text.lower()

        # =====================================================================
        # Step B: Processing Pipeline
        # =====================================================================
        # 1. Run PDF structural forensics on invoice
        struct_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{inv_id}/analyze",
            json={"analyzer_id": "pdf-structural-analyzer"},
        )
        assert struct_resp.status_code == 201
        assert struct_resp.json()["processing_run"]["status"] == "SUCCEEDED"

        # 2. Run OCR on invoice (digital) and receipt (scanned)
        ocr_inv_resp = client.post(f"/api/v1/cases/{case_id}/documents/{inv_id}/ocr")
        assert ocr_inv_resp.status_code == 201

        ocr_rec_resp = client.post(f"/api/v1/cases/{case_id}/documents/{rec_id}/ocr")
        assert ocr_rec_resp.status_code == 201

        # 3. Run document classification
        class_resp = client.post(f"/api/v1/cases/{case_id}/documents/{inv_id}/classification")
        assert class_resp.status_code == 200
        assert class_resp.json()["document_id"] == inv_id

        # 4. Run structured field extraction
        extract_resp = client.post(f"/api/v1/cases/{case_id}/documents/{inv_id}/extraction")
        assert extract_resp.status_code == 200
        assert extract_resp.json()["document_id"] == inv_id

        # 5. Run Entity Resolution & Relationship Detection
        resolve_resp = client.post(f"/api/v1/cases/{case_id}/entity-resolution")
        assert resolve_resp.status_code in (200, 201)

        rel_resp = client.post(f"/api/v1/cases/{case_id}/relationships")
        assert rel_resp.status_code in (200, 201)

        # 6. Run Cross-Document Consistency Analysis with discrepancy
        consistency_resp = client.post(
            f"/api/v1/cases/{case_id}/consistency/analyze",
            json={
                "monetary_tolerance": "0.00",
                "parameters": {
                    "transactions": [
                        {
                            "amount": "11000.00",
                            "currency": "USD",
                            "description": "Payment for INV-2026-9001",
                            "transaction_date": "2026-11-12",
                            "reference": "TXN-9941",
                        }
                    ]
                },
            },
        )
        assert consistency_resp.status_code in (200, 201)

        # 7. Verify processing history
        runs_resp = client.get(f"/api/v1/cases/{case_id}/processing-runs?document_id={inv_id}")
        assert runs_resp.status_code == 200
        runs_data = runs_resp.json()
        assert len(runs_data["items"]) >= 1

        # 8. Verify failed processing does not corrupt original document
        fail_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{inv_id}/analyze",
            json={"analyzer_id": "nonexistent_analyzer_999"},
        )
        assert fail_resp.status_code in (400, 404, 422)

        # Confirm document record and download remain uncorrupted
        check_dl = client.get(f"/api/v1/cases/{case_id}/documents/{inv_id}/download")
        assert check_dl.status_code == 200
        assert check_dl.content == invoice_bytes

        # =====================================================================
        # Step C: Document Examination
        # =====================================================================
        # 1. Retrieve document metadata
        doc_details_resp = client.get(f"/api/v1/cases/{case_id}/documents/{inv_id}")
        assert doc_details_resp.status_code == 200
        assert doc_details_resp.json()["id"] == inv_id

        # 2. Inspect OCR output
        ocr_out_resp = client.get(f"/api/v1/cases/{case_id}/documents/{inv_id}/ocr/text")
        assert ocr_out_resp.status_code == 200
        ocr_data = ocr_out_resp.json()
        assert ocr_data["total_pages"] >= 1
        assert len(ocr_data["pages"]) >= 1

        # 3. Inspect structured fields
        extract_out_resp = client.get(f"/api/v1/cases/{case_id}/documents/{inv_id}/extraction")
        assert extract_out_resp.status_code == 200

        # 4. Inspect forensic findings
        findings_out_resp = client.get(f"/api/v1/cases/{case_id}/findings?document_id={inv_id}")
        assert findings_out_resp.status_code == 200

        # =====================================================================
        # Step D: Relationship & Graph Exploration
        # =====================================================================
        # 1. Retrieve unified Evidence Graph
        graph_resp = client.get(f"/api/v1/cases/{case_id}/graph")
        assert graph_resp.status_code == 200
        graph_data = graph_resp.json()
        assert graph_data["case_id"] == case_id
        assert graph_data["total_nodes"] >= 3  # Documents + Case
        assert len(graph_data["nodes"]) >= 3

        # Find a document node
        doc_nodes = [n for n in graph_data["nodes"] if n["node_type"] == "DOCUMENT"]
        assert len(doc_nodes) >= 1
        target_doc_node = doc_nodes[0]

        # 2. Expand neighborhood
        nb_resp = client.get(
            f"/api/v1/cases/{case_id}/graph/nodes/{target_doc_node['id']}/neighbors?max_hops=1"
        )
        assert nb_resp.status_code == 200
        nb_data = nb_resp.json()
        assert nb_data["center_node_id"] == target_doc_node["id"]
        assert len(nb_data["nodes"]) >= 1

        # 3. Bounded path exploration
        if len(doc_nodes) >= 2:
            paths_resp = client.get(
                f"/api/v1/cases/{case_id}/graph/paths?source_node_id={doc_nodes[0]['id']}&target_node_id={doc_nodes[1]['id']}&max_depth=3"
            )
            assert paths_resp.status_code == 200
            assert "paths" in paths_resp.json()

        # =====================================================================
        # Step E: Findings & Review
        # =====================================================================
        # 1. Retrieve aggregated case findings
        agg_resp = client.get(f"/api/v1/cases/{case_id}/findings/aggregated")
        assert agg_resp.status_code == 200
        agg_findings = agg_resp.json()
        assert len(agg_findings) >= 1

        finding_to_review = agg_findings[0]
        finding_id = finding_to_review["id"]
        initial_classification = finding_to_review.get("evidentiary_classification")
        assert initial_classification is not None

        # 2. Record human review decision
        review_req = {
            "reviewer_id": "senior-examiner-jones",
            "action": "CONFIRM_OBSERVATION",
            "rationale": "Verified invoice total against signed purchase ledger.",
        }
        review_post_resp = client.post(
            f"/api/v1/cases/{case_id}/findings/aggregated/{finding_id}/reviews",
            json=review_req,
        )
        assert review_post_resp.status_code == 201
        review_result = review_post_resp.json()
        assert review_result["reviewer_id"] == "senior-examiner-jones"
        assert review_result["new_status"] == "CONFIRM_OBSERVATION"

        # 3. Verify review history persistence
        history_resp = client.get(
            f"/api/v1/cases/{case_id}/findings/aggregated/{finding_id}/reviews"
        )
        assert history_resp.status_code == 200
        reviews_list = history_resp.json()
        assert len(reviews_list) >= 1
        assert (reviews_list[-1].get("comment") or reviews_list[-1].get("rationale")) == review_req[
            "rationale"
        ]

        # 4. Verify review updates finding review status
        agg_resp_after = client.get(f"/api/v1/cases/{case_id}/findings/aggregated")
        assert agg_resp_after.status_code == 200
        updated_finding = next(f for f in agg_resp_after.json() if f["id"] == finding_id)
        assert updated_finding["is_reviewed"] is True
        assert updated_finding["review_status"] == "CONFIRM_OBSERVATION"

        # =====================================================================
        # Step F: Dossier Lifecycle & Cryptographic Integrity Verification
        # =====================================================================
        # 1. Generate draft dossier
        gen_dossier_resp = client.post(
            f"/api/v1/cases/{case_id}/dossiers/generate",
            json={
                "created_by": "lead-investigator",
                "scope_and_purpose": "Corporate asset discrepancy and forensic verification",
            },
        )
        assert gen_dossier_resp.status_code == 201
        dossier_data = gen_dossier_resp.json()
        dossier_id = dossier_data["id"]

        assert dossier_data["status"] == DossierStatus.DRAFT.value
        assert dossier_data["version"] == 1
        assert len(dossier_data["sections"]) == 12

        # 2. Finalize and freeze the dossier snapshot
        finalize_resp = client.post(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/finalize",
            json={"user_id": "lead-investigator"},
        )
        assert finalize_resp.status_code == 200
        finalized_dossier = finalize_resp.json()

        assert finalized_dossier["status"] == DossierStatus.APPROVED.value
        content_hash = finalized_dossier["content_hash"]
        assert content_hash is not None
        assert len(content_hash) == 64

        # 3. Cryptographic Verification: Recompute hash from payload and assert exact equality
        recomputed_hash = compute_canonical_content_hash(finalized_dossier["dossier_payload"])
        assert recomputed_hash == content_hash, "Deterministic canonical hash mismatch!"

        # 4. Export Vector PDF
        pdf_export_resp = client.get(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/export?format=pdf"
        )
        assert pdf_export_resp.status_code == 200
        assert pdf_export_resp.headers["content-type"] == "application/pdf"
        pdf_bytes = pdf_export_resp.content
        assert pdf_bytes.startswith(b"%PDF-")

        # Verify PDF structure with pikepdf
        with pikepdf.open(io.BytesIO(pdf_bytes)) as exported_pdf:
            assert len(exported_pdf.pages) >= 1

        # 5. Export Structured JSON
        json_export_resp = client.get(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/export?format=json"
        )
        assert json_export_resp.status_code == 200
        assert json_export_resp.headers["content-type"] == "application/json"
        exported_json = json.loads(json_export_resp.content.decode("utf-8"))
        assert exported_json["dossier_id"] == dossier_id
        assert exported_json["content_hash"] == content_hash

        # 6. Verify archived-case restrictions on dossier mutations
        archive_resp = client.post(f"/api/v1/cases/{case_id}/archive")
        assert archive_resp.status_code == 200
        assert archive_resp.json()["status"] == CaseStatus.ARCHIVED.value

        # A) Recording review on archived case must fail
        post_arch_review = client.post(
            f"/api/v1/cases/{case_id}/findings/aggregated/{finding_id}/reviews",
            json=review_req,
        )
        assert post_arch_review.status_code in (400, 422)
        assert "archived" in post_arch_review.text.lower()

        # B) Generating new dossier on archived case must fail
        post_arch_dossier = client.post(
            f"/api/v1/cases/{case_id}/dossiers/generate",
            json={"created_by": "lead-investigator"},
        )
        assert post_arch_dossier.status_code in (400, 422)
        assert "archived" in post_arch_dossier.text.lower()

        # C) Finalizing dossier on archived case must fail
        post_arch_finalize = client.post(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/finalize",
            json={"user_id": "lead-investigator"},
        )
        assert post_arch_finalize.status_code in (400, 422)
        assert "archived" in post_arch_finalize.text.lower()

        # D) Reading existing finalized dossiers and exports must remain accessible
        arch_pdf_get = client.get(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/export?format=pdf"
        )
        assert arch_pdf_get.status_code == 200
        assert arch_pdf_get.content == pdf_bytes
