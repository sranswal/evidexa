"""Integration tests for Visual Forensics (ELA & Copy-Move) engines through REST APIs."""

import io
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    AuditEventType,
    EvidenceType,
    FindingCategory,
    PipelineStatus,
)
from document_intelligence.infrastructure.persistence.models import (
    AuditEventModel,
    EvidenceNodeModel,
    ForensicFindingModel,
)
from tests.fixtures.visual_factory import (
    build_clean_image,
    build_copy_move_image,
    build_ela_spliced_image,
)


def _upload_image_document(
    client: TestClient,
    case_id: str,
    image_bytes: bytes,
    filename: str = "doc.png",
    media_type: str = "image/png",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": (filename, image_bytes, media_type)},
    )
    assert response.status_code == 201, f"Failed uploading image: {response.text}"
    return response.json()


def _upload_pdf_from_image(
    client: TestClient,
    case_id: str,
    image_obj: Any,
    filename: str = "doc.pdf",
) -> dict[str, Any]:
    buf = io.BytesIO()
    image_obj.save(buf, format="PDF", resolution=150.0)
    pdf_bytes = buf.getvalue()

    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, f"Failed uploading PDF: {response.text}"
    return response.json()


class TestVisualForensicsIntegration:
    """End-to-end integration tests for ELA and Copy-Move forensic engines."""

    def test_list_registered_analyzers(self, client: TestClient) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Analyzer Discovery Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        resp = client.get(f"/api/v1/cases/{case_id}/analyzers")
        assert resp.status_code == 200
        analyzers = resp.json()
        analyzer_ids = {a["analyzer_id"] for a in analyzers}

        assert "pdf-structural-analyzer" in analyzer_ids
        assert "ela-analyzer" in analyzer_ids
        assert "copy-move-analyzer" in analyzer_ids

    def test_ela_analysis_on_spliced_pdf_end_to_end(
        self, client: TestClient, db_session: Session
    ) -> None:
        # 1. Create case
        case_resp = client.post("/api/v1/cases", json={"title": "ELA Spliced Document Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Upload synthetic spliced PDF
        spliced_img = build_ela_spliced_image(400, 400)
        doc = _upload_pdf_from_image(client, case_id, spliced_img, "spliced_invoice.pdf")
        doc_id = doc["id"]

        # 3. Trigger ELA analysis via REST API
        analyze_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze",
            json={"analyzer_id": "ela-analyzer", "options": {"ela_quality": 90}},
        )
        assert analyze_resp.status_code == 201
        result = analyze_resp.json()

        run = result["processing_run"]
        assert run["status"] == PipelineStatus.SUCCEEDED.value
        assert run["pipeline_name"] == "Visual Error Level Analysis (ELA) Engine"
        run_id = run["id"]

        # 4. Check findings and evidence in DB
        findings = (
            db_session.query(ForensicFindingModel)
            .filter_by(case_id=case_id, processing_run_id=run_id)
            .all()
        )
        assert len(findings) >= 1
        finding = findings[0]
        assert finding.category == FindingCategory.VISUAL_ANOMALY.value
        assert finding.source_component == "ela-analyzer"
        # Honest confidence: numeric confidence must be None
        assert finding.confidence is None
        assert finding.categorical_confidence in {"low", "medium"}

        # Check evidence node
        evidence_nodes = (
            db_session.query(EvidenceNodeModel)
            .filter_by(case_id=case_id, processing_run_id=run_id)
            .all()
        )
        assert len(evidence_nodes) >= 1
        ev = evidence_nodes[0]
        assert ev.evidence_type == EvidenceType.VISUAL_REGION.value
        assert ev.bounding_box is not None
        assert 0.0 <= ev.bounding_box["x"] <= 1.0
        assert 0.0 <= ev.bounding_box["y"] <= 1.0

        # Check artifact heatmap exists in storage and matches SHA-256
        payload = ev.node_metadata.get("evidence_payload", {})
        art_key = payload.get("artifact_key") or payload.get("artifact_path")
        if art_key:
            from document_intelligence.infrastructure.storage.filesystem import (
                FilesystemDocumentStorage,
            )

            storage = FilesystemDocumentStorage()
            art_file = storage.get_artifact_path(art_key)
            assert art_file.exists()
            assert art_file.stat().st_size > 0
            if payload.get("artifact_sha256"):
                import hashlib

                assert (
                    hashlib.sha256(art_file.read_bytes()).hexdigest().lower()
                    == payload["artifact_sha256"]
                )

        # 5. Check audit events
        audit_events = (
            db_session.query(AuditEventModel)
            .filter_by(case_id=case_id)
            .order_by(AuditEventModel.sequence_number)
            .all()
        )
        event_types = [e.event_type for e in audit_events]
        assert AuditEventType.PROCESSING_RUN_STARTED.value in event_types
        assert AuditEventType.PROCESSING_RUN_COMPLETED.value in event_types

    def test_copy_move_analysis_on_cloned_pdf_end_to_end(
        self, client: TestClient, db_session: Session
    ) -> None:
        # 1. Create case
        case_resp = client.post("/api/v1/cases", json={"title": "Copy-Move Cloned Document Case"})
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Upload synthetic cloned document PDF
        cloned_img = build_copy_move_image(600, 600)
        doc = _upload_pdf_from_image(client, case_id, cloned_img, "cloned_stamp.pdf")
        doc_id = doc["id"]

        # 3. Trigger Copy-Move analysis via REST API
        analyze_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze",
            json={"analyzer_id": "copy-move-analyzer", "options": {}},
        )
        assert analyze_resp.status_code == 201
        result = analyze_resp.json()

        run = result["processing_run"]
        assert run["status"] == PipelineStatus.SUCCEEDED.value
        assert run["pipeline_name"] == "Visual Copy-Move Forgery Detection Engine"
        run_id = run["id"]

        # 4. Check findings and evidence in DB
        findings = (
            db_session.query(ForensicFindingModel)
            .filter_by(case_id=case_id, processing_run_id=run_id)
            .all()
        )
        assert len(findings) >= 1
        finding = findings[0]
        assert finding.category == FindingCategory.DUPLICATE_CONTENT.value
        assert finding.source_component == "copy-move-analyzer"
        assert finding.confidence is None

        # Check evidence node
        evidence_nodes = (
            db_session.query(EvidenceNodeModel)
            .filter_by(case_id=case_id, processing_run_id=run_id)
            .all()
        )
        assert len(evidence_nodes) >= 1
        ev = evidence_nodes[0]
        assert ev.evidence_type == EvidenceType.VISUAL_REGION.value
        assert ev.bounding_box is not None  # Duplicate box

        # Both source and duplicate bounding boxes preserved in payload
        payload = ev.node_metadata.get("evidence_payload", {})
        assert "source_bounding_box" in payload
        assert "duplicate_bounding_box" in payload
        assert "displacement_dx" in payload
        assert "displacement_dy" in payload

        # Check artifact visualization exists in storage and matches SHA-256
        art_key = payload.get("artifact_key") or payload.get("artifact_path")
        if art_key:
            from document_intelligence.infrastructure.storage.filesystem import (
                FilesystemDocumentStorage,
            )

            storage = FilesystemDocumentStorage()
            art_file = storage.get_artifact_path(art_key)
            assert art_file.exists()
            assert art_file.stat().st_size > 0
            if payload.get("artifact_sha256"):
                import hashlib

                assert (
                    hashlib.sha256(art_file.read_bytes()).hexdigest().lower()
                    == payload["artifact_sha256"]
                )

    def test_clean_document_produces_no_visual_findings(
        self, client: TestClient, db_session: Session
    ) -> None:
        case_resp = client.post("/api/v1/cases", json={"title": "Clean Document Check"})
        case_id = case_resp.json()["id"]

        clean_img = build_clean_image(300, 300)
        doc = _upload_pdf_from_image(client, case_id, clean_img, "clean.pdf")
        doc_id = doc["id"]

        # Copy-Move on clean document
        cm_resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze",
            json={"analyzer_id": "copy-move-analyzer"},
        )
        assert cm_resp.status_code == 201
        cm_result = cm_resp.json()
        assert cm_result["processing_run"]["status"] == PipelineStatus.SUCCEEDED.value
        assert len(cm_result["findings"]) == 0
