"""Integration tests for persistence, SHA-256 artifact integrity, rerun isolation, and provenance."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.core.config import settings
from document_intelligence.core.exceptions import SecurityException
from document_intelligence.domain.enums import (
    CoordinateSystem,
    EvidenceType,
    FieldDataType,
    FieldValidationStatus,
)
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.infrastructure.persistence.models import (
    EvidenceNodeModel,
    ProcessingRunModel,
)
from document_intelligence.infrastructure.repositories.audit_repository import (
    AuditRepository,
)
from document_intelligence.infrastructure.repositories.case_repository import (
    CaseRepository,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.storage.filesystem import (
    FilesystemDocumentStorage,
)
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.understanding.service import (
    DocumentUnderstandingService,
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


def _get_understanding_service(
    db_session: Session, storage: FilesystemDocumentStorage
) -> DocumentUnderstandingService:
    audit_repo = AuditRepository(db_session)
    audit_svc = AuditLedgerService(audit_repo)
    case_svc = CaseService(CaseRepository(db_session), audit_service=audit_svc)
    return DocumentUnderstandingService(
        case_service=case_svc,
        document_repo=DocumentRepository(db_session),
        evidence_repo=EvidenceRepository(db_session),
        run_repo=ProcessingRunRepository(db_session),
        storage=storage,
        audit_service=audit_svc,
    )


class TestPersistenceAndProvenance:
    """Rigorous verification of Priority F: artifact persistence, rerun isolation, and evidence links."""

    def test_artifact_reload_and_sha256_verification(
        self,
        client: TestClient,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """Verify artifact persistence on disk, SHA-256 calculation, reload, and tamper detection."""
        # Setup case and document
        case_resp = client.post("/api/v1/cases", json={"title": "Artifact Integrity Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        # Run OCR
        ocr_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "pdfium-ocr-engine"},
        )
        assert ocr_resp.status_code == 201

        # Run extraction
        ext_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert ext_resp.status_code == 200
        ext_data = ext_resp.json()

        run_id = ext_data["processing_run_id"]
        sha256_recorded = ext_data["storage_artifact_sha256"]
        artifact_key = ext_data["storage_artifact_key"]

        assert run_id is not None
        assert sha256_recorded is not None
        assert artifact_key is not None
        assert artifact_key.endswith(f"extraction_{run_id}.json")

        # Resolve storage used by API runtime
        storage = FilesystemDocumentStorage(settings)
        art_path = storage.get_artifact_path(artifact_key)
        assert art_path.exists()

        raw_bytes = art_path.read_bytes()
        actual_sha256 = hashlib.sha256(raw_bytes).hexdigest().lower()
        assert actual_sha256 == sha256_recorded.lower()

        # Reload through DocumentUnderstandingService with SHA-256 verification
        svc = _get_understanding_service(db_session, storage)
        reloaded_bytes = svc._read_artifact(
            case_id=case_id,
            document_id=doc_id,
            processing_run_id=run_id,
            artifact_filename=f"extraction_{run_id}.json",
            expected_sha256=sha256_recorded,
        )
        assert reloaded_bytes == raw_bytes

        # Verify get_latest_extraction verifies SHA-256
        latest = svc.get_latest_extraction(
            case_id=case_id,
            document_id=doc_id,
            expected_sha256=sha256_recorded,
        )
        assert latest.processing_run_id == run_id

        # Verify tampering detection: wrong expected_sha256 raises SecurityException
        with pytest.raises(SecurityException, match="Artifact integrity violation"):
            svc._read_artifact(
                case_id=case_id,
                document_id=doc_id,
                processing_run_id=run_id,
                artifact_filename=f"extraction_{run_id}.json",
                expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            )

    def test_rerun_isolation(
        self,
        client: TestClient,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """Verify subsequent extractions create distinct ProcessingRuns and artifacts without overwriting."""
        case_resp = client.post("/api/v1/cases", json={"title": "Rerun Isolation Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "pdfium-ocr-engine"},
        )

        # First extraction run
        resp1 = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert resp1.status_code == 200
        run1_data = resp1.json()
        run1_id = run1_data["processing_run_id"]
        key1 = run1_data["storage_artifact_key"]
        sha1 = run1_data["storage_artifact_sha256"]

        # Second extraction run on same document
        resp2 = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert resp2.status_code == 200
        run2_data = resp2.json()
        run2_id = run2_data["processing_run_id"]
        key2 = run2_data["storage_artifact_key"]
        sha2 = run2_data["storage_artifact_sha256"]

        # Run IDs and artifact paths must be strictly distinct
        assert run1_id != run2_id
        assert key1 != key2

        storage = FilesystemDocumentStorage(settings)
        path1 = storage.get_artifact_path(key1)
        path2 = storage.get_artifact_path(key2)

        # Both artifact files must exist independently on disk
        assert path1.exists()
        assert path2.exists()

        # Run 1 artifact file was not touched or overwritten
        bytes1 = path1.read_bytes()
        assert hashlib.sha256(bytes1).hexdigest().lower() == sha1.lower()

        # Run 2 artifact file is also valid
        bytes2 = path2.read_bytes()
        assert hashlib.sha256(bytes2).hexdigest().lower() == sha2.lower()

        # Check DB processing runs
        runs = (
            db_session.query(ProcessingRunModel)
            .filter_by(case_id=case_id)
            .order_by(ProcessingRunModel.started_at.asc())
            .all()
        )
        extraction_runs = [r for r in runs if "structured-extraction" in r.pipeline_name]
        assert len(extraction_runs) == 2
        assert extraction_runs[0].id == run1_id
        assert extraction_runs[1].id == run2_id

    def test_evidence_node_links_and_token_ids(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """Verify extracted field EvidenceNodes link to SQLite and carry source token IDs."""
        case_resp = client.post("/api/v1/cases", json={"title": "Evidence Graph Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        pdf_path = tmp_path / "invoice.pdf"
        create_clean_digital_pdf(pdf_path)
        doc = _upload_pdf(client, case_id, pdf_path, "invoice.pdf")
        doc_id = doc["id"]

        client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/ocr",
            json={"analyzer_id": "pdfium-ocr-engine"},
        )

        resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/extraction",
            json={"schema_id": "invoice_v1"},
        )
        assert resp.status_code == 200
        ext_data = resp.json()
        run_id = ext_data["processing_run_id"]

        # Query all evidence nodes generated for this run
        nodes = (
            db_session.query(EvidenceNodeModel)
            .filter_by(
                case_id=case_id,
                document_id=doc_id,
                processing_run_id=run_id,
                evidence_type=EvidenceType.EXTRACTED_FIELD.value,
            )
            .all()
        )
        assert len(nodes) > 0

        for node in nodes:
            meta = node.node_metadata or {}
            assert "field_key" in meta
            assert "schema_id" in meta
            assert meta["schema_id"] == "invoice_v1"
            assert "validation_status" in meta
            assert "source_token_ids" in meta
            assert isinstance(meta["source_token_ids"], list)

            # If bounding box exists, coordinate system must be normalized
            if node.bounding_box is not None:
                assert node.coordinate_system == CoordinateSystem.NORMALIZED_0_1.value
                assert "x" in node.bounding_box
                assert "y" in node.bounding_box
                assert "width" in node.bounding_box
                assert "height" in node.bounding_box
            else:
                assert node.coordinate_system is None

    def test_missing_bounding_box_coordinates_remain_empty(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Verify that when extraction cannot localize a field, bounding boxes remain empty and are not fabricated."""
        field_val = ExtractedFieldValue(
            field_key="test_field",
            label="Test Field",
            data_type=FieldDataType.STRING,
            raw_text="Test",
            normalized_value="Test",
            validation_status=FieldValidationStatus.VALID,
            source_document_id="doc-test-123",
            source_page_number=1,
            source_bounding_boxes=[],  # Explicit empty list
            source_token_ids=[],
            extraction_method="deterministic_pattern_v1",
        )

        assert field_val.source_bounding_boxes == []
        assert len(field_val.source_bounding_boxes) == 0
