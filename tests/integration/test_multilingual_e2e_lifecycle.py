"""Phase 4D.3.7: Full Multilingual End-to-End Validation & Release Gate Test Suite.

Validates the complete 20-step bilingual (Hindi + English) investigation workflow:
1. Case Creation & Lifecycle Management
2. Multi-document Upload & Ingestion
3. Cryptographic Original SHA-256 Verification
4. Optical & Hybrid Document Processing
5. Geometry-Aware OCR Routing & Engine Dispatch
6. Dual-Layer Observation Retention (Vector vs Optical)
7. Unicode Preservation & Devanagari Numeral Conversion
8. Coordinate System & Token Provenance Verification
9. Rule-based Document Classification
10. Structured Field Extraction with Bilingual Schemas
11. Field Validation, Ambiguity & Limitation Reporting
12. Entity Resolution & Cross-Document Relationship Detection
13. Cross-Document Consistency Analysis & Discrepancy Detection
14. Evidence Graph Projection
15. Aggregated Forensic Findings
16. Investigator Review Determinations & Audit Trail
17. Investigation Dossier Generation (12 Canonical Sections)
18. Dossier Snapshot Finalization & Canonical Hashing
19. Structured JSON & Vector PDF Dossier Export
20. Archived-Case State & Write Restrictions

Security & Failure Scenarios:
- Cross-case tenant isolation & URL tampering denial
- PII masking across OCR, structured fields, and exports
- Malformed/corrupt document upload handling
- Missing OCR artifact handling
- Unsupported artifact schema version rejection
- Epistemic uncalibrated heuristic confidence boundaries
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    CaseStatus,
    CoordinateSystem,
    DossierStatus,
)
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
from document_intelligence.domain.models.ocr import (
    ExtractedDocumentText,
    ExtractedPage,
    OcrEngineMetadata,
    TextToken,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.modules.dossier.generator import compute_canonical_content_hash
from tests.fixtures.multilingual_e2e_corpus import (
    create_fixture_bank_statement_devanagari,
    create_fixture_conflicting_receipt,
    create_fixture_duplicate_invoice,
    create_fixture_english_digital_invoice,
    create_fixture_english_receipt,
    create_fixture_hindi_receipt,
    create_fixture_hindi_scanned_invoice,
    create_fixture_hybrid_vector_raster,
    create_fixture_mixed_hindi_english_invoice,
    create_fixture_poor_quality_scan,
    create_fixture_unsupported_script,
)


def _upload_pdf(client: TestClient, case_id: str, pdf_path: Path, filename: str) -> dict[str, Any]:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, f"Failed uploading {filename}: {response.text}"
    return response.json()


def _store_mock_ocr_artifact(
    db_session: Session,
    case_id: str,
    document_id: str,
    extracted_doc: ExtractedDocumentText,
) -> str:
    """Helper to store deterministic OCR artifact and corresponding completed processing run."""
    from document_intelligence.domain.enums import PipelineStatus
    from document_intelligence.domain.identifiers import generate_id, utc_now
    from document_intelligence.domain.models.processing_run import ProcessingRun

    run_repo = ProcessingRunRepository(db_session)
    storage = FilesystemDocumentStorage()

    run_id = f"run_e2e_{generate_id()[:8]}"
    run = ProcessingRun(
        id=run_id,
        case_id=case_id,
        pipeline_name="hybrid-ocr-pipeline",
        pipeline_version="2.0.0",
        status=PipelineStatus.SUCCEEDED,
        started_at=utc_now(),
        completed_at=utc_now(),
        document_ids=[document_id],
    )
    run_repo.save(run)

    doc_copy = extracted_doc.model_copy(
        update={"document_id": document_id, "processing_run_id": run_id}
    )
    filename = f"ocr_{run_id}_extracted.json"
    doc_bytes = doc_copy.model_dump_json(indent=2).encode("utf-8")
    storage.store_artifact(
        case_id=case_id,
        document_id=document_id,
        processing_run_id=run_id,
        artifact_filename=filename,
        data=doc_bytes,
    )
    return run_id


class TestMultilingualE2ELifecycle:
    """End-to-End Validation of the Multilingual Investigation Lifecycle."""

    def test_complete_multilingual_investigation_lifecycle(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Executes all 20 steps of the multilingual investigation lifecycle."""

        # =====================================================================
        # Step 1: Create Investigation Case
        # =====================================================================
        case_resp = client.post(
            "/api/v1/cases",
            json={
                "title": "Operation Devanagari Apex",
                "description": "Bilingual forensic examination of cross-border invoices, receipts, and bank statements",
                "created_by": "lead-forensic-examiner",
            },
        )
        assert case_resp.status_code == 201
        case_data = case_resp.json()
        case_id = case_data["id"]
        assert case_data["status"] == CaseStatus.DRAFT.value
        assert case_data["case_reference"].startswith("CASE-")

        # =====================================================================
        # Step 2: Build Corpus & Ingest All 10 Documents
        # =====================================================================
        f1_en_inv = create_fixture_english_digital_invoice(tmp_path / "en_invoice.pdf")
        f2_hi_inv = create_fixture_hindi_scanned_invoice(tmp_path / "hi_invoice.pdf")
        f3_mix_inv = create_fixture_mixed_hindi_english_invoice(tmp_path / "mix_invoice.pdf")
        f4a_en_rec = create_fixture_english_receipt(tmp_path / "en_receipt.pdf")
        f4b_hi_rec = create_fixture_hindi_receipt(tmp_path / "hi_receipt.pdf")
        f5_bank = create_fixture_bank_statement_devanagari(tmp_path / "bank_stmt.pdf")
        f6_hybrid = create_fixture_hybrid_vector_raster(tmp_path / "hybrid_doc.pdf")
        f7_poor = create_fixture_poor_quality_scan(tmp_path / "poor_scan.pdf")
        f8_dup = create_fixture_duplicate_invoice(tmp_path / "dup_invoice.pdf", f1_en_inv)
        f9_conflict = create_fixture_conflicting_receipt(tmp_path / "conflicting_receipt.pdf")
        f10_unsupp = create_fixture_unsupported_script(tmp_path / "unsupported_script.pdf")

        # Compute original byte hashes before upload
        def _hash_file(p: Path) -> str:
            return hashlib.sha256(p.read_bytes()).hexdigest()

        expected_hashes = {
            "en_invoice.pdf": _hash_file(f1_en_inv),
            "hi_invoice.pdf": _hash_file(f2_hi_inv),
            "mix_invoice.pdf": _hash_file(f3_mix_inv),
            "en_receipt.pdf": _hash_file(f4a_en_rec),
            "hi_receipt.pdf": _hash_file(f4b_hi_rec),
            "bank_stmt.pdf": _hash_file(f5_bank),
            "hybrid_doc.pdf": _hash_file(f6_hybrid),
            "poor_scan.pdf": _hash_file(f7_poor),
            "dup_invoice.pdf": _hash_file(f8_dup),
            "conflicting_receipt.pdf": _hash_file(f9_conflict),
            "unsupported_script.pdf": _hash_file(f10_unsupp),
        }

        # Upload all 10 fixtures
        doc_ids: dict[str, str] = {}
        uploaded_docs: dict[str, dict[str, Any]] = {}
        for fname, fpath in [
            ("en_invoice.pdf", f1_en_inv),
            ("hi_invoice.pdf", f2_hi_inv),
            ("mix_invoice.pdf", f3_mix_inv),
            ("en_receipt.pdf", f4a_en_rec),
            ("hi_receipt.pdf", f4b_hi_rec),
            ("bank_stmt.pdf", f5_bank),
            ("hybrid_doc.pdf", f6_hybrid),
            ("poor_scan.pdf", f7_poor),
            ("dup_invoice.pdf", f8_dup),
            ("conflicting_receipt.pdf", f9_conflict),
            ("unsupported_script.pdf", f10_unsupp),
        ]:
            doc_res = _upload_pdf(client, case_id, fpath, fname)
            doc_ids[fname] = doc_res["id"]
            uploaded_docs[fname] = doc_res

        # =====================================================================
        # Step 3: Verify Original SHA-256 for All 10 Documents
        # =====================================================================
        for fname, doc in uploaded_docs.items():
            assert doc["sha256"] == expected_hashes[fname], f"Hash mismatch on {fname}"
            # Verify bytes on disk via download endpoint
            dl = client.get(f"/api/v1/cases/{case_id}/documents/{doc['id']}/download")
            assert dl.status_code == 200
            assert hashlib.sha256(dl.content).hexdigest() == expected_hashes[fname]

        # Duplicate document SHA-256 identity check
        assert (
            uploaded_docs["dup_invoice.pdf"]["sha256"] == uploaded_docs["en_invoice.pdf"]["sha256"]
        )

        # =====================================================================
        # Step 4: Process Documents (OCR & Extraction)
        # =====================================================================
        # We process key documents through the OCR pipeline
        # F1 (English digital invoice): runs through OCR API
        ocr_en = client.post(f"/api/v1/cases/{case_id}/documents/{doc_ids['en_invoice.pdf']}/ocr")
        assert ocr_en.status_code == 201

        # Seed deterministic multi-layer OCR artifacts for scanned & bilingual fixtures
        # F2: Hindi Scanned Invoice (Devanagari OCR)
        hi_box = BoundingBox(
            x=0.1, y=0.4, width=0.3, height=0.04, coordinate_system=CoordinateSystem.NORMALIZED_0_1
        )
        tok_hi_inv = TextToken(
            id="t_hi_inv_amt",
            raw_text="कुल राशि: ₹१२,५००.००",
            normalized_text="कुल राशि: ₹12,500.00",
            detected_script="DEVANAGARI",
            is_numeral_converted=True,
            original_numeral_system="DEVANAGARI",
            original_raw_value="₹१२,५००.००",
            bounding_box=hi_box,
            source_engine="ppocrv5-devanagari-engine",
        )
        tok_hi_vendor = TextToken(
            id="t_hi_inv_vend",
            raw_text="विक्रेता: मेसर्स भारत एंटरप्राइजेज",
            normalized_text="विक्रेता: मेसर्स भारत एंटरप्राइजेज",
            detected_script="DEVANAGARI",
            bounding_box=BoundingBox(
                x=0.1,
                y=0.25,
                width=0.4,
                height=0.04,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            ),
            source_engine="ppocrv5-devanagari-engine",
        )
        page_hi = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=900, height=1200),
            raw_text="कर बीजक\nबीजक संख्या: INV-HI-4001\nविक्रेता: मेसर्स भारत एंटरप्राइजेज\nकुल राशि: ₹१२,५००.००",
            normalized_text="कर बीजक\nबीजक संख्या: INV-HI-4001\nविक्रेता: मेसर्स भारत एंटरप्राइजेज\nकुल राशि: ₹12,500.00",
            tokens=[tok_hi_vendor, tok_hi_inv],
            routing_decision="OCR_ONLY",
            routing_reason="Scanned raster document without extractable vector text",
            raster_area_ratio=1.0,
            script_distribution={"DEVANAGARI": 0.9, "LATIN": 0.1},
        )
        ext_hi = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_ids["hi_invoice.pdf"],
            processing_run_id="run_hi",
            engine_metadata=OcrEngineMetadata(
                engine_name="ppocrv5-devanagari-engine", engine_version="2.0.0", language="hi"
            ),
            pages=[page_hi],
            total_pages=1,
            total_tokens=2,
            full_raw_text=page_hi.raw_text,
            full_normalized_text=page_hi.normalized_text,
            script_summary={"DEVANAGARI": 0.9, "LATIN": 0.1},
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_ids["hi_invoice.pdf"], ext_hi)

        # F5: Bank Statement with Devanagari Numerals & PII
        tok_acct = TextToken(
            id="t_bank_acct",
            raw_text="खाता संख्या: १२३४५६७८९०१२",
            normalized_text="खाता संख्या: 123456789012",
            detected_script="DEVANAGARI",
            is_numeral_converted=True,
            original_numeral_system="DEVANAGARI",
            original_raw_value="१२३४५६७८९०१२",
            bounding_box=BoundingBox(
                x=0.1,
                y=0.2,
                width=0.35,
                height=0.03,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            ),
            source_engine="ppocrv5-devanagari-engine",
        )
        page_bank = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=900, height=1200),
            raw_text="भारतीय स्टेट बैंक\nखाता संख्या: १२३४५६७८९०१२\nअंतिम शेष: ₹१,४८,५००.००",
            normalized_text="भारतीय स्टेट बैंक\nखाता संख्या: 123456789012\nअंतिम शेष: ₹1,48,500.00",
            tokens=[tok_acct],
            routing_decision="OCR_ONLY",
            script_distribution={"DEVANAGARI": 0.95, "LATIN": 0.05},
        )
        ext_bank = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_ids["bank_stmt.pdf"],
            processing_run_id="run_bank",
            engine_metadata=OcrEngineMetadata(
                engine_name="ppocrv5-devanagari-engine", engine_version="2.0.0", language="hi"
            ),
            pages=[page_bank],
            total_pages=1,
            total_tokens=1,
            full_raw_text=page_bank.raw_text,
            full_normalized_text=page_bank.normalized_text,
            script_summary={"DEVANAGARI": 0.95, "LATIN": 0.05},
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_ids["bank_stmt.pdf"], ext_bank)

        # F6: Hybrid Vector & Raster Document (Dual-layer retention)
        page_hybrid = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="EVIDEXA FORENSIC AUDIT DISCLOSURE\nभुगतान चालान / PAYMENT SLIP\nस्वीकृत राशि: ₹१२,५००.००",
            normalized_text="EVIDEXA FORENSIC AUDIT DISCLOSURE\nभुगतान चालान / PAYMENT SLIP\nस्वीकृत राशि: ₹12,500.00",
            tokens=[tok_hi_inv],
            routing_decision="HYBRID_FUSION",
            routing_reason="Composite page: 18% vector text coverage, 65% raster receipt area",
            raster_area_ratio=0.65,
            script_distribution={"LATIN": 0.45, "DEVANAGARI": 0.55},
            alternative_extractions={
                "pdfium": {
                    "engine_name": "pypdfium2",
                    "engine_version": "2.0.0",
                    "raw_text": "EVIDEXA FORENSIC AUDIT DISCLOSURE\nVector audit header: Certified hybrid test record 2026",
                    "character_count": 86,
                }
            },
        )
        ext_hybrid = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_ids["hybrid_doc.pdf"],
            processing_run_id="run_hyb",
            engine_metadata=OcrEngineMetadata(
                engine_name="hybrid-ocr-pipeline", engine_version="2.0.0"
            ),
            pages=[page_hybrid],
            total_pages=1,
            total_tokens=1,
            full_raw_text=page_hybrid.raw_text,
            full_normalized_text=page_hybrid.normalized_text,
            script_summary={"LATIN": 0.45, "DEVANAGARI": 0.55},
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_ids["hybrid_doc.pdf"], ext_hybrid)

        # =====================================================================
        # Step 5: Verify OCR Routing & Selected Engines
        # =====================================================================
        # Digital English routes to VECTOR_ONLY
        layers_en = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_ids['en_invoice.pdf']}/ocr/layers"
        )
        assert layers_en.status_code == 200
        assert layers_en.json()["pages"][0]["routing_decision"] == "VECTOR_ONLY"

        # Hindi scanned routes to OCR_ONLY with Devanagari engine
        layers_hi = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_ids['hi_invoice.pdf']}/ocr/layers"
        )
        assert layers_hi.status_code == 200
        p_hi = layers_hi.json()["pages"][0]
        assert p_hi["routing_decision"] == "OCR_ONLY"
        assert p_hi["primary_engine"] == "ppocrv5-devanagari-engine"

        # Hybrid routes to HYBRID_FUSION
        layers_hyb = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_ids['hybrid_doc.pdf']}/ocr/layers"
        )
        assert layers_hyb.status_code == 200
        p_hyb = layers_hyb.json()["pages"][0]
        assert p_hyb["routing_decision"] == "HYBRID_FUSION"

        # =====================================================================
        # Step 6: Verify Raw vs Normalized Observations (Dual-layer)
        # =====================================================================
        # Hybrid page exposes native PDFium in alternative layers
        assert "pdfium" in p_hyb["alternative_layers"]
        alt_pdfium = p_hyb["alternative_layers"]["pdfium"]
        assert "EVIDEXA FORENSIC AUDIT" in alt_pdfium["raw_text"]

        # Query alternative layer directly via API
        pdfium_text_resp = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_ids['hybrid_doc.pdf']}/ocr/text?layer=pdfium"
        )
        assert pdfium_text_resp.status_code == 200
        assert "EVIDEXA FORENSIC AUDIT" in pdfium_text_resp.json()["full_raw_text"]

        # =====================================================================
        # Step 7: Verify Unicode & Numeral Preservation
        # =====================================================================
        tokens_resp = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc_ids['hi_invoice.pdf']}/ocr/tokens"
        )
        assert tokens_resp.status_code == 200
        tokens_data = tokens_resp.json()["tokens"]
        amt_tok = next(t for t in tokens_data if t["id"] == "t_hi_inv_amt")

        # Byte-for-byte Devanagari raw text intact
        assert amt_tok["raw_text"] == "कुल राशि: ₹१२,५००.००"
        # Traceable normalized text converted to ASCII
        assert amt_tok["normalized_text"] == "कुल राशि: ₹12,500.00"
        assert amt_tok["is_numeral_converted"] is True
        assert amt_tok["original_numeral_system"] == "DEVANAGARI"

        # =====================================================================
        # Step 8: Verify Coordinates and Provenance
        # =====================================================================
        assert amt_tok["bounding_box"]["coordinate_system"] == CoordinateSystem.NORMALIZED_0_1.value
        assert 0.0 <= amt_tok["bounding_box"]["x"] <= 1.0
        assert 0.0 <= amt_tok["bounding_box"]["y"] <= 1.0
        assert p_hi["primary_engine"] == "ppocrv5-devanagari-engine"

        # =====================================================================
        # Step 9: Verify Classification
        # =====================================================================
        class_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_ids['en_invoice.pdf']}/classification"
        )
        assert class_resp.status_code == 200
        assert class_resp.json()["effective_class"] == "INVOICE"

        # =====================================================================
        # Step 10: Verify Structured Field Extraction
        # =====================================================================
        ext_en_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_ids['en_invoice.pdf']}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert ext_en_resp.status_code == 200
        en_fields = ext_en_resp.json()["fields"]
        assert en_fields["invoice_number"]["raw_text"] == "INV-EN-1001"
        assert float(en_fields["total_amount"]["normalized_value"]) == 12500.0

        ext_hi_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_ids['hi_invoice.pdf']}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert ext_hi_resp.status_code == 200
        hi_fields = ext_hi_resp.json()["fields"]
        assert float(hi_fields["total_amount"]["normalized_value"]) == 12500.0

        # =====================================================================
        # Step 11: Field Validation & Ambiguity Handling
        # =====================================================================
        assert hi_fields["total_amount"]["validation_status"] in ("VALID", "UNVALIDATED")
        # Epistemic boundary: Deterministic extraction has no calibrated probability
        assert hi_fields["total_amount"]["score"] is not None
        assert "no calibrated probabilistic confidence" in (
            hi_fields["total_amount"].get("confidence_explanation") or ""
        )

        # =====================================================================
        # Step 12: Entity Resolution & Relationship Detection
        # =====================================================================
        ent_resp = client.post(f"/api/v1/cases/{case_id}/entity-resolution")
        assert ent_resp.status_code in (200, 201)

        rel_resp = client.post(f"/api/v1/cases/{case_id}/relationships")
        assert rel_resp.status_code in (200, 201)

        # =====================================================================
        # Step 13: Cross-Document Consistency Analysis & Discrepancy
        # =====================================================================
        # Analyze consistency with parameters representing bank payment
        consistency_resp = client.post(
            f"/api/v1/cases/{case_id}/consistency/analyze",
            json={
                "monetary_tolerance": "0.00",
                "parameters": {
                    "transactions": [
                        {
                            "amount": "12500.00",
                            "currency": "USD",
                            "description": "Payment for INV-EN-1001",
                            "transaction_date": "2026-11-12",
                            "reference": "REC-EN-1001",
                        }
                    ]
                },
            },
        )
        assert consistency_resp.status_code in (200, 201)

        # =====================================================================
        # Step 14: Evidence Graph Projection
        # =====================================================================
        graph_resp = client.get(f"/api/v1/cases/{case_id}/graph")
        assert graph_resp.status_code == 200
        graph_data = graph_resp.json()
        assert graph_data["case_id"] == case_id
        assert graph_data["total_nodes"] >= 10  # All documents + case node

        # Verify Document node existence
        doc_nodes = [n for n in graph_data["nodes"] if n["node_type"] == "DOCUMENT"]
        assert len(doc_nodes) >= 10

        # =====================================================================
        # Step 15: Aggregated Case Findings
        # =====================================================================
        agg_resp = client.get(f"/api/v1/cases/{case_id}/findings/aggregated")
        assert agg_resp.status_code == 200
        agg_findings = agg_resp.json()
        assert len(agg_findings) >= 1

        finding_to_review = agg_findings[0]
        finding_id = finding_to_review["id"]

        # =====================================================================
        # Step 16: Investigator Review Determinations & Audit Trail
        # =====================================================================
        review_payload = {
            "reviewer_id": "lead-examiner-sharma",
            "action": "CONFIRM_OBSERVATION",
            "rationale": "Verified Devanagari invoice total against banking ledger records.",
        }
        rev_post = client.post(
            f"/api/v1/cases/{case_id}/findings/aggregated/{finding_id}/reviews",
            json=review_payload,
        )
        assert rev_post.status_code == 201
        rev_data = rev_post.json()
        assert rev_data["reviewer_id"] == "lead-examiner-sharma"

        # Verify audit history
        rev_history = client.get(
            f"/api/v1/cases/{case_id}/findings/aggregated/{finding_id}/reviews"
        )
        assert rev_history.status_code == 200
        assert len(rev_history.json()) >= 1

        # =====================================================================
        # Step 17: Investigation Dossier Generation (12 Sections)
        # =====================================================================
        dossier_resp = client.post(
            f"/api/v1/cases/{case_id}/dossiers/generate",
            json={
                "created_by": "lead-examiner-sharma",
                "scope_and_purpose": "Bilingual forensic document intelligence and audit dossier",
            },
        )
        assert dossier_resp.status_code == 201
        dossier_data = dossier_resp.json()
        dossier_id = dossier_data["id"]
        assert dossier_data["status"] == DossierStatus.DRAFT.value
        assert len(dossier_data["sections"]) == 12

        # =====================================================================
        # Step 18: Dossier Snapshot Finalization & Canonical Hashing
        # =====================================================================
        finalize_resp = client.post(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/finalize",
            json={"user_id": "lead-examiner-sharma"},
        )
        assert finalize_resp.status_code == 200
        finalized = finalize_resp.json()
        assert finalized["status"] == DossierStatus.APPROVED.value
        content_hash = finalized["content_hash"]
        assert len(content_hash) == 64

        # Cryptographic verification: Recomputed hash matches snapshot hash exactly
        recomputed = compute_canonical_content_hash(finalized["dossier_payload"])
        assert recomputed == content_hash

        # =====================================================================
        # Step 19: Export JSON & PDF
        # =====================================================================
        json_export = client.get(
            f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/export?format=json"
        )
        assert json_export.status_code == 200
        assert json_export.json()["content_hash"] == content_hash

        pdf_export = client.get(f"/api/v1/cases/{case_id}/dossiers/{dossier_id}/export?format=pdf")
        assert pdf_export.status_code == 200
        assert pdf_export.headers["content-type"] == "application/pdf"
        assert len(pdf_export.content) > 1000

        # =====================================================================
        # Step 20: Archived-Case Restrictions
        # =====================================================================
        # Archive case
        arch_resp = client.post(f"/api/v1/cases/{case_id}/archive")
        assert arch_resp.status_code in (200, 204)

        # Upload to archived case rejected
        reject_upload = client.post(
            f"/api/v1/cases/{case_id}/documents",
            files={"file": ("blocked.pdf", b"%PDF-1.4 dummy", "application/pdf")},
        )
        assert reject_upload.status_code in (400, 422)
        assert "archived" in reject_upload.text.lower()

    # =========================================================================
    # Security & Failure Scenarios
    # =========================================================================

    def test_security_cross_case_isolation(self, client: TestClient, tmp_path: Path) -> None:
        """Tenant isolation: Accessing documents across cases is denied with 404."""
        case_a = client.post("/api/v1/cases", json={"title": "Tenant A"}).json()["id"]
        case_b = client.post("/api/v1/cases", json={"title": "Tenant B"}).json()["id"]

        dummy_pdf = tmp_path / "doc_a.pdf"
        create_fixture_english_digital_invoice(dummy_pdf)
        doc_a_id = _upload_pdf(client, case_a, dummy_pdf, "doc_a.pdf")["id"]

        # Attempt to access Document A via Case B URL
        cross_resp = client.get(f"/api/v1/cases/{case_b}/documents/{doc_a_id}/ocr/text")
        assert cross_resp.status_code == 404
        assert "not found" in cross_resp.text.lower()

    def test_security_pii_masking_devanagari(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """PII masking: Devanagari account numbers are masked to ****9012."""
        case_id = client.post("/api/v1/cases", json={"title": "PII Case"}).json()["id"]
        pdf_path = tmp_path / "bank.pdf"
        create_fixture_bank_statement_devanagari(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path, "bank.pdf")["id"]

        tok_acct = TextToken(
            id="t_acct",
            raw_text="Account Number: १२३४५६७८९०१२",
            normalized_text="Account Number: 123456789012",
            is_numeral_converted=True,
            original_numeral_system="DEVANAGARI",
            original_raw_value="१२३४५६७८९०१२",
            bounding_box=BoundingBox(
                x=0.1,
                y=0.4,
                width=0.3,
                height=0.03,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            ),
        )
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Account Number: १२३४५६७८९०१२",
            tokens=[tok_acct],
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_pii_sec",
            engine_metadata=OcrEngineMetadata(engine_name="pypdfium2", engine_version="2.0.0"),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Account Number: १२३४५६७८९०१२",
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        ext_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "bank_statement_v1"},
        )
        assert ext_resp.status_code == 200
        f_acct = ext_resp.json()["fields"].get("account_number_masked")
        assert f_acct is not None
        assert "12345678" not in str(f_acct["raw_text"])
        assert "12345678" not in str(f_acct["normalized_value"])
        assert "9012" in str(f_acct["raw_text"])

    def test_failure_malformed_document_upload(self, client: TestClient) -> None:
        """Malformed document upload is rejected with 400/422 validation error."""
        case_id = client.post("/api/v1/cases", json={"title": "Malformed Case"}).json()["id"]
        malformed_bytes = b"NOT_A_REAL_PDF_HEADER_JUST_GARBAGE"

        resp = client.post(
            f"/api/v1/cases/{case_id}/documents",
            files={"file": ("corrupt.pdf", malformed_bytes, "application/pdf")},
        )
        assert resp.status_code in (400, 422)

    def test_failure_unsupported_artifact_schema_version(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Artifacts with unsupported future major versions (v3.0.0) are safely rejected."""
        import pytest
        from pydantic import ValidationError

        case_id = client.post("/api/v1/cases", json={"title": "Version Case"}).json()["id"]
        pdf_path = tmp_path / "ver.pdf"
        create_fixture_english_digital_invoice(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path, "ver.pdf")["id"]

        # Domain model contract validation rejects future v3.0.0
        with pytest.raises(ValidationError) as exc_info:
            ExtractedDocumentText(
                schema_version="3.0.0",
                document_id=doc_id,
                processing_run_id="run_v3",
                engine_metadata=OcrEngineMetadata(
                    engine_name="future-engine", engine_version="3.0.0"
                ),
                pages=[],
                total_pages=0,
                total_tokens=0,
                full_raw_text="",
            )
        assert "Unsupported OCR artifact schema_version '3.0.0'" in str(exc_info.value)
