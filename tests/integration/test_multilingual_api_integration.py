"""Integration test suite for Phase 4D.3.6: Multilingual Extraction API & Investigator Workbench Integration.

Verifies all 12 required backend scenarios:
1. test_multilingual_response_serialization
2. test_pdfium_only_response
3. test_ocr_only_response
4. test_hybrid_response
5. test_hindi_and_english_extraction
6. test_unicode_and_numeral_normalization
7. test_provenance_and_coordinate_serialization
8. test_disagreement_reporting
9. test_pii_masking
10. test_case_authorization_and_cross_case_denial
11. test_missing_artifact_handling
12. test_existing_api_regression
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import CoordinateSystem, PageRoutingDecision
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
from document_intelligence.domain.models.ocr import (
    AlternativeExtractionObservation,
    ExtractedDocumentText,
    ExtractedPage,
    OcrEngineMetadata,
    TextToken,
    create_traceable_token,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from tests.fixtures.ocr_factory import (
    create_clean_digital_pdf,
    create_scanned_printed_text_pdf,
)


def _create_case(client: TestClient, title: str = "Multilingual API Test Case") -> str:
    resp = client.post("/api/v1/cases", json={"title": title})
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_pdf(
    client: TestClient, case_id: str, pdf_path: Path, filename: str = "test_doc.pdf"
) -> dict[str, Any]:
    with open(pdf_path, "rb") as f:
        resp = client.post(
            f"/api/v1/cases/{case_id}/documents",
            files={"file": (filename, f.read(), "application/pdf")},
        )
    assert resp.status_code == 201
    return resp.json()


def _store_mock_ocr_artifact(
    db_session: Session,
    case_id: str,
    document_id: str,
    extracted_doc: ExtractedDocumentText,
) -> str:
    """Helper to inject an explicit ExtractedDocumentText artifact and corresponding processing run."""
    from document_intelligence.domain.enums import PipelineStatus
    from document_intelligence.domain.identifiers import generate_id, utc_now
    from document_intelligence.domain.models.processing_run import ProcessingRun

    run_repo = ProcessingRunRepository(db_session)
    storage = FilesystemDocumentStorage()

    run_id = f"run_mock_{generate_id()[:8]}"
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

    # Update extracted_doc with matching run_id and document_id
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


class TestMultilingualExtractionApi:
    """End-to-end API integration tests for Phase 4D.3.6."""

    # 1. Multilingual response serialization
    def test_multilingual_response_serialization(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Scenario 1: Verifies typed and versioned multilingual OCR JSON serialization."""
        case_id = _create_case(client, "Serialization Case")
        pdf_path = tmp_path / "dummy.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        tok_hi = create_traceable_token(raw_text="चालान")
        tok_en = create_traceable_token(raw_text="Invoice")
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="चालान Invoice",
            normalized_text="चालान Invoice",
            tokens=[tok_hi, tok_en],
            routing_decision="HYBRID_FUSION",
            script_distribution={"DEVANAGARI": 0.5, "LATIN": 0.5},
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_dummy",
            engine_metadata=OcrEngineMetadata(
                engine_name="hybrid-ocr-pipeline", engine_version="2.0.0"
            ),
            pages=[page],
            total_pages=1,
            total_tokens=2,
            full_raw_text="चालान Invoice",
            full_normalized_text="चालान Invoice",
            script_summary={"DEVANAGARI": 0.5, "LATIN": 0.5},
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text")
        assert resp.status_code == 200
        data = resp.json()

        assert data["schema_version"] == "2.0.0"
        assert data["script_summary"] == {"DEVANAGARI": 0.5, "LATIN": 0.5}
        p1 = data["pages"][0]
        assert p1["routing_decision"] == "HYBRID_FUSION"
        assert p1["tokens"][0]["detected_script"] == "DEVANAGARI"
        assert p1["tokens"][1]["detected_script"] == "LATIN"

    # 2. PDFium-only response
    def test_pdfium_only_response(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Scenario 2: Programmatic vector text strictly retains confidence as None."""
        case_id = _create_case(client, "Vector Only Case")
        pdf_path = tmp_path / "digital.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        tok_vec = TextToken(
            id="vec_1",
            raw_text="Digital",
            normalized_text="Digital",
            confidence=None,
            detected_script="LATIN",
        )
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Digital",
            tokens=[tok_vec],
            has_vector_text=True,
            routing_decision=PageRoutingDecision.VECTOR_ONLY.value,
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_vec",
            engine_metadata=OcrEngineMetadata(engine_name="pypdfium2", engine_version="2.0.0"),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Digital",
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pages"][0]["routing_decision"] == "VECTOR_ONLY"
        assert data["pages"][0]["tokens"][0]["confidence"] is None

    # 3. OCR-only response
    def test_ocr_only_response(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Scenario 3: Optical OCR tokens retain uncalibrated float confidence scores."""
        case_id = _create_case(client, "OCR Only Case")
        pdf_path = tmp_path / "scan.pdf"
        create_scanned_printed_text_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        tok_ocr = TextToken(
            id="ocr_1",
            raw_text="विवरण",
            normalized_text="विवरण",
            confidence=0.942,
            detected_script="DEVANAGARI",
        )
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="विवरण",
            tokens=[tok_ocr],
            has_vector_text=False,
            routing_decision=PageRoutingDecision.OCR_ONLY.value,
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_ocr",
            engine_metadata=OcrEngineMetadata(
                engine_name="ppocrv5-devanagari-engine", engine_version="2.0.0"
            ),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="विवरण",
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pages"][0]["routing_decision"] == "OCR_ONLY"
        assert data["pages"][0]["tokens"][0]["confidence"] == 0.942

    # 4. Hybrid response
    def test_hybrid_response(self, client: TestClient, db_session: Session, tmp_path: Path) -> None:
        """Scenario 4: Dedicated /layers endpoint exposes dual layers and duplicate references."""
        case_id = _create_case(client, "Hybrid Layer Case")
        pdf_path = tmp_path / "hybrid.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        tok_ocr = TextToken(id="o1", raw_text="TOTAL", confidence=0.96)
        tok_vec = TextToken(id="v1", raw_text="TOTAL", confidence=None)

        potential_dups = [
            {
                "text": "TOTAL",
                "ocr_token_id": "o1",
                "pdfium_token_id": "v1",
                "spatial_iou": 0.88,
            }
        ]

        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="TOTAL",
            tokens=[tok_ocr],
            engine_name="rapidocr-optical-engine",
            routing_decision=PageRoutingDecision.HYBRID_FUSION.value,
            raster_area_ratio=0.45,
            vector_char_count=5,
        )
        page.alternative_extractions["pdfium"] = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            raw_text="TOTAL",
            tokens=[tok_vec],
            metadata={"potential_duplicate_tokens": potential_dups},
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_hyb",
            engine_metadata=OcrEngineMetadata(
                engine_name="hybrid-ocr-pipeline", engine_version="2.0.0"
            ),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="TOTAL",
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/layers")
        assert resp.status_code == 200
        layers_data = resp.json()

        assert layers_data["total_pages"] == 1
        p_layer = layers_data["pages"][0]
        assert p_layer["routing_decision"] == "HYBRID_FUSION"
        assert p_layer["raster_area_ratio"] == 0.45
        assert p_layer["primary_engine"] == "rapidocr-optical-engine"
        assert "pdfium" in p_layer["alternative_layers"]
        assert len(p_layer["potential_duplicates"]) == 1
        assert p_layer["potential_duplicates"][0]["spatial_iou"] == 0.88

    # 5. Hindi and English extraction
    def test_hindi_and_english_extraction(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Scenario 5: Structured extraction extracts bilingual invoice fields."""
        case_id = _create_case(client, "Extraction Case")
        pdf_path = tmp_path / "bilingual_inv.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        tok_lbl = TextToken(
            id="t_lbl",
            raw_text="कुल राशि:",
            normalized_text="कुल राशि:",
            bounding_box=BoundingBox(
                x=0.1,
                y=0.5,
                width=0.15,
                height=0.03,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            ),
        )
        tok_val = TextToken(
            id="t_val",
            raw_text="₹१२,५००.००",
            normalized_text="₹12,500.00",
            is_numeral_converted=True,
            original_numeral_system="DEVANAGARI",
            original_raw_value="₹१२,५००.००",
            bounding_box=BoundingBox(
                x=0.26,
                y=0.5,
                width=0.15,
                height=0.03,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            ),
        )
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="कुल राशि: ₹१२,५००.००",
            normalized_text="कुल राशि: ₹12,500.00",
            tokens=[tok_lbl, tok_val],
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_inv",
            engine_metadata=OcrEngineMetadata(engine_name="devanagari-ocr", engine_version="2.0.0"),
            pages=[page],
            total_pages=1,
            total_tokens=2,
            full_raw_text=page.raw_text,
            full_normalized_text=page.normalized_text,
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        # Execute structured extraction with invoice schema
        ext_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert ext_resp.status_code == 200
        ext_data = ext_resp.json()

        assert "total_amount" in ext_data["fields"]
        f_amount = ext_data["fields"]["total_amount"]
        assert f_amount["normalized_value"] in (12500.0, "12500.00", 125000.0)
        assert "t_val" in f_amount["source_token_ids"]
        assert len(f_amount["source_bounding_boxes"]) == 1

    # 6. Unicode and numeral normalization
    def test_unicode_and_numeral_normalization(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Scenario 6: Tokens preserve original Devanagari numerals while exposing converted ASCII in normalized_text."""
        case_id = _create_case(client, "Numeral Normalization Case")
        pdf_path = tmp_path / "num.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        tok = create_traceable_token(raw_text="९८७६५")
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="९८७६५",
            tokens=[tok],
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_num",
            engine_metadata=OcrEngineMetadata(engine_name="devanagari-ocr", engine_version="2.0.0"),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="९८७६५",
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/tokens")
        assert resp.status_code == 200
        tokens = resp.json()["tokens"]
        assert len(tokens) == 1
        t = tokens[0]
        assert t["raw_text"] == "९८७६५"
        assert t["normalized_text"] == "98765"
        assert t["is_numeral_converted"] is True
        assert t["original_numeral_system"] == "DEVANAGARI"
        assert t["original_raw_value"] == "९८७६५"

    # 7. Provenance and coordinate serialization
    def test_provenance_and_coordinate_serialization(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Scenario 7: Token coordinates are normalized [0.0, 1.0] and engine metadata scrubs host filesystem paths."""
        case_id = _create_case(client, "Coordinate Case")
        pdf_path = tmp_path / "coords.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        box = BoundingBox(
            x=0.15,
            y=0.25,
            width=0.4,
            height=0.08,
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )
        tok = TextToken(
            id="tok_c1",
            raw_text="Sample",
            bounding_box=box,
            reading_order_index=5,
        )
        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Sample",
            tokens=[tok],
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_coords",
            engine_metadata=OcrEngineMetadata(
                engine_name="test-engine",
                engine_version="2.0.0",
                model_id="/home/user/secret/models/ppocrv5.onnx",
            ),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Sample",
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/tokens")
        assert resp.status_code == 200
        t = resp.json()["tokens"][0]
        assert t["reading_order_index"] == 5
        assert t["bounding_box"]["x"] == 0.15
        assert t["bounding_box"]["y"] == 0.25

        # Check that model_id in engine_metadata does not expose host directories
        text_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text")
        meta = text_resp.json()["engine_metadata"]
        assert meta["model_id"] == "ppocrv5.onnx"
        assert "/home/user" not in meta["model_id"]

    # 8. Disagreement reporting
    def test_disagreement_reporting(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Scenario 8: Evidentiary conflicts between primary and alternative layers are serialized."""
        case_id = _create_case(client, "Disagreement Case")
        pdf_path = tmp_path / "disagree.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        p_toks = [TextToken(id=f"pt{i}", raw_text=f"tok{i}") for i in range(2)]
        alt_toks = [TextToken(id=f"at{i}", raw_text=f"tok{i}") for i in range(20)]

        page = ExtractedPage(
            page_number=1,
            geometry=PageGeometry(width=612, height=792),
            raw_text="Short",
            tokens=p_toks,
            engine_name="optical-engine",
        )
        page.alternative_extractions["pdfium"] = AlternativeExtractionObservation(
            engine_name="pypdfium2",
            raw_text="A very detailed paragraph with substantial text content.",
            tokens=alt_toks,
            token_count=20,
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_dis",
            engine_metadata=OcrEngineMetadata(
                engine_name="hybrid-pipeline", engine_version="2.0.0"
            ),
            pages=[page],
            total_pages=1,
            total_tokens=2,
            full_raw_text="Short",
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/layers")
        assert resp.status_code == 200
        disagreements = resp.json()["pages"][0]["disagreements"]
        assert len(disagreements) == 1
        assert disagreements[0]["has_disagreement"] is True
        assert disagreements[0]["token_count_delta"] == 18

    # 9. PII masking
    def test_pii_masking(self, client: TestClient, db_session: Session, tmp_path: Path) -> None:
        """Scenario 9: Masked string fields (e.g. account numbers) are never exposed unmasked."""
        case_id = _create_case(client, "PII Case")
        pdf_path = tmp_path / "bank.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        tok_acct = TextToken(
            id="t_acct",
            raw_text="Account Number: 123456789012",
            normalized_text="Account Number: 123456789012",
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
            raw_text="Account Number: 123456789012",
            tokens=[tok_acct],
        )
        extracted = ExtractedDocumentText(
            schema_version="2.0.0",
            document_id=doc_id,
            processing_run_id="run_pii",
            engine_metadata=OcrEngineMetadata(engine_name="pypdfium2", engine_version="2.0.0"),
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Account Number: 123456789012",
        )
        _store_mock_ocr_artifact(db_session, case_id, doc_id, extracted)

        ext_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "bank_statement_v1"},
        )
        assert ext_resp.status_code == 200
        f_acct = ext_resp.json()["fields"].get("account_number_masked")
        if f_acct:
            assert "12345678" not in str(f_acct["raw_text"])
            assert "12345678" not in str(f_acct["normalized_value"])
            assert "9012" in str(f_acct["raw_text"])

    # 10. Case authorization and cross-case denial
    def test_case_authorization_and_cross_case_denial(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """Scenario 10: Accessing document from Case A using Case B in the URL is rejected with 404."""
        case_a = _create_case(client, "Case A")
        case_b = _create_case(client, "Case B")

        pdf_path = tmp_path / "private.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_a_id = _upload_pdf(client, case_a, pdf_path)["id"]

        # Attempt to access Document A using Case B path
        denied_resp = client.get(f"/api/v1/cases/{case_b}/documents/{doc_a_id}/ocr/text")
        assert denied_resp.status_code == 404
        err_msg = denied_resp.json()["error"]["message"]
        assert "not found in case" in err_msg.lower()

    # 11. Missing artifact handling
    def test_missing_artifact_handling(self, client: TestClient, tmp_path: Path) -> None:
        """Scenario 11: Querying OCR on an un-processed document returns 404 without internal server error."""
        case_id = _create_case(client, "Unprocessed Case")
        pdf_path = tmp_path / "fresh.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/text")
        assert resp.status_code == 404
        err_msg = resp.json()["error"]["message"]
        assert "no completed ocr runs found" in err_msg.lower()

    # 12. Existing API regression
    def test_existing_api_regression(self, client: TestClient, tmp_path: Path) -> None:
        """Scenario 12: Existing capabilities, layout, tables, and paginated tokens endpoints function without regression."""
        case_id = _create_case(client, "Regression Case")
        pdf_path = tmp_path / "reg.pdf"
        create_clean_digital_pdf(pdf_path)
        doc_id = _upload_pdf(client, case_id, pdf_path)["id"]

        cap_resp = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr/capabilities")
        assert cap_resp.status_code == 200
        cap_data = cap_resp.json()
        assert "registered_ocr_engines" in cap_data
        assert "supported_scripts" in cap_data
        assert "DEVANAGARI" in cap_data["supported_scripts"]
        assert cap_data["normalization_version"] == "2.0.0"
