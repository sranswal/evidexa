"""Security and tamper-detection tests for document forensic processing."""

from pathlib import Path

from fastapi.testclient import TestClient

from document_intelligence.infrastructure.persistence.models import DocumentModel

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "pdf"


class TestForensicSecuritySafeguards:
    """Validate security invariants, pre/post hash checks, and cross-case isolation."""

    def test_mime_spoofing_rejected_at_ingestion(self, client: TestClient) -> None:
        """Reject non-PDF file uploaded with application/pdf MIME type."""
        case_resp = client.post("/api/v1/cases", json={"title": "MIME Spoof Case"})
        case_id = case_resp.json()["id"]

        txt_file = FIXTURES_DIR / "fixture_wrong_media_type.txt"
        assert txt_file.exists()

        with open(txt_file, "rb") as f:
            resp = client.post(
                f"/api/v1/cases/{case_id}/documents",
                files={"file": ("fake.pdf", f.read(), "application/pdf")},
            )
        assert resp.status_code == 400
        assert "signature mismatch" in resp.text.lower() or "security" in resp.text.lower()

    def test_hash_tampering_prior_to_analysis_triggers_security_exception(
        self, client: TestClient, db_session
    ) -> None:
        """If a stored document's file bytes are tampered with on disk, analysis aborts with SecurityException."""
        # 1. Upload valid PDF
        case_resp = client.post("/api/v1/cases", json={"title": "Tampering Test Case"})
        case_id = case_resp.json()["id"]

        pdf_path = FIXTURES_DIR / "fixture_normal.pdf"
        with open(pdf_path, "rb") as f:
            doc_resp = client.post(
                f"/api/v1/cases/{case_id}/documents",
                files={"file": ("normal.pdf", f.read(), "application/pdf")},
            )
        assert doc_resp.status_code == 201
        doc_id = doc_resp.json()["id"]

        # 2. Tamper with the database's recorded sha256 to simulate undetected file modification
        doc_model = db_session.get(DocumentModel, doc_id)
        assert doc_model is not None
        doc_model.sha256 = "0" * 64
        db_session.commit()

        # 3. Attempt analysis: should fail with security violation / 400 error
        resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze")
        assert resp.status_code in [400, 500]
        assert (
            "integrity" in resp.text.lower()
            or "sha-256" in resp.text.lower()
            or "hash" in resp.text.lower()
        )

    def test_cross_case_document_analysis_prevented(self, client: TestClient) -> None:
        """Prevent analyzing a document using another case's endpoint."""
        # Create Case A with Document A
        case_a = client.post("/api/v1/cases", json={"title": "Case A"}).json()["id"]
        pdf_path = FIXTURES_DIR / "fixture_normal.pdf"
        with open(pdf_path, "rb") as f:
            doc_a = client.post(
                f"/api/v1/cases/{case_a}/documents",
                files={"file": ("doc_a.pdf", f.read(), "application/pdf")},
            ).json()["id"]

        # Create Case B
        case_b = client.post("/api/v1/cases", json={"title": "Case B"}).json()["id"]

        # Attempt to analyze doc_a under case_b
        resp = client.post(f"/api/v1/cases/{case_b}/documents/{doc_a}/analyze")
        assert resp.status_code in [400, 404, 422]

    def test_snapshot_tampering_during_analysis_detected(self, client: TestClient) -> None:
        """If ephemeral analysis snapshot is modified during analyzer execution, abort with SecurityException."""
        from document_intelligence.domain.enums import AuditEventType, PipelineStatus
        from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer
        from document_intelligence.modules.forensics.interfaces.registry import default_registry
        from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
        from document_intelligence.modules.forensics.schemas.analyzer_output import AnalyzerOutput

        class TamperingMockAnalyzer(ForensicAnalyzer):
            @property
            def analyzer_id(self) -> str:
                return "mock-tampering-analyzer"

            @property
            def display_name(self) -> str:
                return "Mock Tampering Analyzer"

            @property
            def name(self) -> str:
                return self.display_name

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def supported_media_types(self) -> set[str]:
                return {"application/pdf"}

            @property
            def supported_capabilities(self) -> list[str]:
                return ["test"]

            def can_analyze(self, media_type: str) -> bool:
                return media_type == "application/pdf"

            def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
                # Maliciously append bytes to the snapshot file!
                with open(input_data.file_path, "ab") as f:
                    f.write(b"\nTAMPERED_MALICIOUS_BYTES\n")
                return AnalyzerOutput(
                    analyzer_id=self.analyzer_id,
                    analyzer_name=self.display_name,
                    analyzer_version=self.version,
                    status=PipelineStatus.SUCCEEDED,
                    execution_duration_ms=5.0,
                    capabilities_executed=[],
                    observations=[],
                    raw_metadata={},
                    limitations=[],
                    errors=[],
                )

        tampering_analyzer = TamperingMockAnalyzer()
        default_registry.register(tampering_analyzer)

        case_resp = client.post("/api/v1/cases", json={"title": "Snapshot Tamper Case"})
        case_id = case_resp.json()["id"]

        pdf_path = FIXTURES_DIR / "fixture_normal.pdf"
        with open(pdf_path, "rb") as f:
            doc_id = client.post(
                f"/api/v1/cases/{case_id}/documents",
                files={"file": ("normal.pdf", f.read(), "application/pdf")},
            ).json()["id"]

        resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze",
            json={"analyzer_id": "mock-tampering-analyzer"},
        )
        assert resp.status_code in [400, 500]
        assert "integrity violation" in resp.text.lower() or "snapshot" in resp.text.lower()

        # Check audit trail recorded INTEGRITY_VERIFICATION_FAILED
        audit_resp = client.get(f"/api/v1/cases/{case_id}/audit-events")
        events = audit_resp.json()["items"]
        assert any(
            e["event_type"] == AuditEventType.INTEGRITY_VERIFICATION_FAILED.value for e in events
        )

    def test_case_archival_prohibits_new_operations_and_preserves_records(
        self, client: TestClient
    ) -> None:
        """Archiving a case halts document ingestion and analysis while preserving complete evidence history."""
        # 1. Create case, ingest document and analyze
        case_resp = client.post("/api/v1/cases", json={"title": "Archival Invariant Case"})
        case_id = case_resp.json()["id"]

        pdf_path = FIXTURES_DIR / "fixture_normal.pdf"
        with open(pdf_path, "rb") as f:
            doc_id = client.post(
                f"/api/v1/cases/{case_id}/documents",
                files={"file": ("normal.pdf", f.read(), "application/pdf")},
            ).json()["id"]

        analyze_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze")
        assert analyze_resp.status_code == 201

        # 2. Archive case via API
        archive_resp = client.post(f"/api/v1/cases/{case_id}/archive")
        assert archive_resp.status_code == 200
        assert archive_resp.json()["status"] == "ARCHIVED"

        # 3. Ingesting new document into archived case must fail
        with open(pdf_path, "rb") as f:
            reject_ingest = client.post(
                f"/api/v1/cases/{case_id}/documents",
                files={"file": ("extra.pdf", f.read(), "application/pdf")},
            )
        assert reject_ingest.status_code in [400, 422]
        assert "archived" in reject_ingest.text.lower()

        # 4. Triggering analysis on existing document in archived case must fail
        reject_analyze = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze")
        assert reject_analyze.status_code in [400, 422]
        assert "archived" in reject_analyze.text.lower()

        # 5. Verify records preserved: processing runs, findings, audit events
        runs = client.get(f"/api/v1/cases/{case_id}/processing-runs").json()["items"]
        assert len(runs) >= 1

        findings = client.get(f"/api/v1/cases/{case_id}/findings").json()["items"]
        assert isinstance(findings, list)

        audit_events = client.get(f"/api/v1/cases/{case_id}/audit-events").json()["items"]
        assert any(
            e["event_type"] == "CASE_STATUS_CHANGED"
            and e["payload"].get("new_status") == "ARCHIVED"
            for e in audit_events
        )

    def test_stale_run_recovery_lifecycle(self, db_session) -> None:
        """Detect and recover stale RUNNING processing runs left behind by crash or abrupt termination."""
        from datetime import UTC, datetime

        from document_intelligence.core.config import settings
        from document_intelligence.domain.enums import AuditEventType, PipelineStatus
        from document_intelligence.domain.identifiers import generate_id
        from document_intelligence.infrastructure.persistence.models import (
            CaseModel,
            ProcessingRunModel,
        )
        from document_intelligence.infrastructure.repositories.audit_repository import (
            AuditRepository,
        )
        from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
        from document_intelligence.infrastructure.repositories.document_repository import (
            DocumentRepository,
        )
        from document_intelligence.infrastructure.repositories.evidence_repository import (
            EvidenceRepository,
        )
        from document_intelligence.infrastructure.repositories.finding_repository import (
            FindingRepository,
        )
        from document_intelligence.infrastructure.repositories.processing_run_repository import (
            ProcessingRunRepository,
        )
        from document_intelligence.infrastructure.storage.filesystem import (
            FilesystemDocumentStorage,
        )
        from document_intelligence.modules.audit.ledger import AuditLedgerService
        from document_intelligence.modules.forensics.application.processing_service import (
            ForensicProcessingService,
        )

        case_id = generate_id()
        case_model = CaseModel(
            id=case_id,
            case_reference="CASE-STALE-TEST",
            title="Stale Recovery Test",
            status="ACTIVE",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(case_model)

        run_id = generate_id()
        stale_run = ProcessingRunModel(
            id=run_id,
            case_id=case_id,
            document_ids=["dummy-doc"],
            pipeline_name="PDF Structural & Byte-Level Forensics Analyzer",
            pipeline_version="0.6.0",
            status=PipelineStatus.RUNNING.value,
            started_at=datetime.now(UTC),
            configuration_snapshot={},
        )
        db_session.add(stale_run)
        db_session.commit()

        audit_repo = AuditRepository(db_session)
        audit_service = AuditLedgerService(audit_repo)
        run_repo = ProcessingRunRepository(db_session)
        storage = FilesystemDocumentStorage(settings)

        service = ForensicProcessingService(
            processing_run_repo=run_repo,
            evidence_repo=EvidenceRepository(db_session),
            finding_repo=FindingRepository(db_session),
            document_repo=DocumentRepository(db_session),
            case_repo=CaseRepository(db_session),
            audit_service=audit_service,
            storage=storage,
        )

        recovered_count = service.recover_stale_runs()
        assert recovered_count >= 1

        updated_run = run_repo.get_by_id(run_id)
        assert updated_run is not None
        assert updated_run.status == PipelineStatus.FAILED
        assert updated_run.error_code == "RUN_INTERRUPTED"
        assert "interrupted" in updated_run.error_message.lower()

        # Verify audit trail contains interruption events
        events, _ = audit_repo.list_by_case(case_id)
        event_types = [e.event_type.value for e in events]
        assert AuditEventType.PROCESSING_RUN_INTERRUPTED.value in event_types
        assert AuditEventType.PROCESSING_RUN_COMPLETED.value in event_types

    def test_concurrent_snapshot_creation_distinct_paths(self, db_session) -> None:
        """Concurrent or multiple analysis runs generate distinct snapshot paths without collisions."""
        import io

        from document_intelligence.core.config import settings
        from document_intelligence.infrastructure.storage.filesystem import (
            FilesystemDocumentStorage,
        )

        storage = FilesystemDocumentStorage(settings)
        sample_bytes = b"%PDF-1.4 sample content for concurrency verification"
        storage_key, _, orig_sha = storage.store_original(
            case_id="case-concurrent",
            document_id="doc-concurrent",
            file_obj=io.BytesIO(sample_bytes),
            declared_filename="sample.pdf",
        )

        try:
            # Create two snapshots for different processing runs
            snap1_path, snap1_sha = storage.create_analysis_snapshot(storage_key, "run-aaa-111")
            snap2_path, snap2_sha = storage.create_analysis_snapshot(storage_key, "run-bbb-222")

            assert snap1_path != snap2_path
            assert snap1_path.exists()
            assert snap2_path.exists()
            assert snap1_sha == orig_sha
            assert snap2_sha == orig_sha

            # Cleanup one snapshot, ensure other remains untouched
            storage.cleanup_analysis_snapshot(snap1_path)
            assert not snap1_path.exists()
            assert snap2_path.exists()

            storage.cleanup_analysis_snapshot(snap2_path)
            assert not snap2_path.exists()
        finally:
            storage.delete_original(storage_key)

    def test_repeated_stale_run_recovery_is_idempotent(self, db_session) -> None:
        """Consecutive invocations of recover_stale_runs do not duplicate failure transitions."""
        from datetime import UTC, datetime

        from document_intelligence.core.config import settings
        from document_intelligence.domain.enums import PipelineStatus
        from document_intelligence.domain.identifiers import generate_id
        from document_intelligence.infrastructure.persistence.models import (
            CaseModel,
            ProcessingRunModel,
        )
        from document_intelligence.infrastructure.repositories.audit_repository import (
            AuditRepository,
        )
        from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
        from document_intelligence.infrastructure.repositories.document_repository import (
            DocumentRepository,
        )
        from document_intelligence.infrastructure.repositories.evidence_repository import (
            EvidenceRepository,
        )
        from document_intelligence.infrastructure.repositories.finding_repository import (
            FindingRepository,
        )
        from document_intelligence.infrastructure.repositories.processing_run_repository import (
            ProcessingRunRepository,
        )
        from document_intelligence.infrastructure.storage.filesystem import (
            FilesystemDocumentStorage,
        )
        from document_intelligence.modules.audit.ledger import AuditLedgerService
        from document_intelligence.modules.forensics.application.processing_service import (
            ForensicProcessingService,
        )

        case_id = generate_id()
        case_model = CaseModel(
            id=case_id,
            case_reference="CASE-IDEMPOTENT-TEST",
            title="Idempotent Stale Test",
            status="ACTIVE",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(case_model)

        run_id = generate_id()
        stale_run = ProcessingRunModel(
            id=run_id,
            case_id=case_id,
            document_ids=["dummy-doc"],
            pipeline_name="PDF Structural & Byte-Level Forensics Analyzer",
            pipeline_version="0.6.0",
            status=PipelineStatus.RUNNING.value,
            started_at=datetime.now(UTC),
            configuration_snapshot={},
        )
        db_session.add(stale_run)
        db_session.commit()

        service = ForensicProcessingService(
            processing_run_repo=ProcessingRunRepository(db_session),
            evidence_repo=EvidenceRepository(db_session),
            finding_repo=FindingRepository(db_session),
            document_repo=DocumentRepository(db_session),
            case_repo=CaseRepository(db_session),
            audit_service=AuditLedgerService(AuditRepository(db_session)),
            storage=FilesystemDocumentStorage(settings),
        )

        # First pass recovers the single abandoned run
        recovered_1 = service.recover_stale_runs()
        assert recovered_1 == 1

        # Second immediate pass discovers 0 abandoned runs (idempotent)
        recovered_2 = service.recover_stale_runs()
        assert recovered_2 == 0

    def test_audit_persistence_failure_aborts_analysis_workflow(
        self, client: TestClient, monkeypatch
    ) -> None:
        """If audit ledger persistence fails during PROCESSING_RUN_STARTED, analysis halts immediately."""
        from document_intelligence.core.exceptions import StorageException
        from document_intelligence.domain.enums import AuditEventType
        from document_intelligence.modules.audit.ledger import AuditLedgerService

        original_record = AuditLedgerService.record_event

        def faulty_record(self, *args, **kwargs):
            if kwargs.get("event_type") == AuditEventType.PROCESSING_RUN_STARTED:
                raise StorageException("Audit storage disk I/O error.")
            return original_record(self, *args, **kwargs)

        monkeypatch.setattr(AuditLedgerService, "record_event", faulty_record)

        case_resp = client.post("/api/v1/cases", json={"title": "Audit Failure Test Case"})
        case_id = case_resp.json()["id"]

        pdf_path = FIXTURES_DIR / "fixture_normal.pdf"
        with open(pdf_path, "rb") as f:
            doc_id = client.post(
                f"/api/v1/cases/{case_id}/documents",
                files={"file": ("normal.pdf", f.read(), "application/pdf")},
            ).json()["id"]

        # Analysis must raise/return error and NOT silently succeed
        analyze_resp = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze")
        assert analyze_resp.status_code in [400, 500]
        assert "audit" in analyze_resp.text.lower() or "storage" in analyze_resp.text.lower()

    def test_partial_success_lifecycle_and_audit(self, client: TestClient) -> None:
        """When an analyzer reports partial warnings alongside observations, status is PARTIALLY_SUCCEEDED."""
        from document_intelligence.domain.enums import AuditEventType, PipelineStatus
        from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer
        from document_intelligence.modules.forensics.interfaces.registry import default_registry
        from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
        from document_intelligence.modules.forensics.schemas.analyzer_output import (
            AnalyzerCapabilityResult,
            AnalyzerObservation,
            AnalyzerOutput,
        )

        class PartialSuccessMockAnalyzer(ForensicAnalyzer):
            @property
            def analyzer_id(self) -> str:
                return "mock-partial-analyzer"

            @property
            def display_name(self) -> str:
                return "Mock Partial Success Analyzer"

            @property
            def name(self) -> str:
                return self.display_name

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def supported_media_types(self) -> set[str]:
                return {"application/pdf"}

            @property
            def supported_capabilities(self) -> list[str]:
                return ["test"]

            def can_analyze(self, media_type: str) -> bool:
                return media_type == "application/pdf"

            def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
                return AnalyzerOutput(
                    analyzer_id=self.analyzer_id,
                    analyzer_name=self.display_name,
                    analyzer_version=self.version,
                    status=PipelineStatus.PARTIALLY_SUCCEEDED,
                    execution_duration_ms=12.0,
                    capabilities_executed=[
                        AnalyzerCapabilityResult(
                            capability_id="test",
                            status="WARNING",
                            error_message="Non-fatal warning",
                        )
                    ],
                    observations=[
                        AnalyzerObservation(
                            capability_id="test",
                            observation_type="test",
                            severity="low",
                            categorical_confidence="low",
                            confidence=None,
                            confidence_source="test",
                            title="Test Warning Observation",
                            description="Test Warning Description",
                        )
                    ],
                    raw_metadata={},
                    limitations=["Secondary stream was unreadable."],
                    errors=["Non-fatal stream warning"],
                )

        default_registry.register(PartialSuccessMockAnalyzer())

        case_resp = client.post("/api/v1/cases", json={"title": "Partial Success Case"})
        case_id = case_resp.json()["id"]

        pdf_path = FIXTURES_DIR / "fixture_normal.pdf"
        with open(pdf_path, "rb") as f:
            doc_id = client.post(
                f"/api/v1/cases/{case_id}/documents",
                files={"file": ("normal.pdf", f.read(), "application/pdf")},
            ).json()["id"]

        resp = client.post(
            f"/api/v1/cases/{case_id}/documents/{doc_id}/analyze",
            json={"analyzer_id": "mock-partial-analyzer"},
        )
        assert resp.status_code == 201
        run = resp.json()["processing_run"]
        assert run["status"] == PipelineStatus.PARTIALLY_SUCCEEDED.value

        # Verify audit ledger recorded PARTIALLY_SUCCEEDED
        audit_resp = client.get(f"/api/v1/cases/{case_id}/audit-events")
        events = audit_resp.json()["items"]
        completed_event = next(
            e for e in events if e["event_type"] == AuditEventType.PROCESSING_RUN_COMPLETED.value
        )
        assert completed_event["payload"]["status"] == PipelineStatus.PARTIALLY_SUCCEEDED.value

    def test_oversized_worker_output_handling(self, tmp_path: Path) -> None:
        """If worker stdout exceeds 1 MB, output extraction safely truncates without unhandled crash."""
        from document_intelligence.domain.enums import PipelineStatus
        from document_intelligence.modules.forensics.adapters.pdf_structural.adapter import (
            PdfStructuralAnalyzer,
        )
        from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput

        analyzer = PdfStructuralAnalyzer()
        dummy_file = tmp_path / "test.pdf"
        dummy_file.write_bytes(b"%PDF-1.4\n%%EOF")

        input_data = AnalyzerInput(
            file_path=dummy_file,
            declared_media_type="application/pdf",
            detected_media_type="application/pdf",
            document_sha256="abc",
            document_id="doc-1",
            case_id="case-1",
            processing_run_id="run-1",
        )

        import subprocess

        # Simulate subprocess returning 2 MB of garbage stdout
        oversized_stdout = "X" * (2 * 1024 * 1024)
        mock_proc = subprocess.CompletedProcess(
            args=["fake"],
            returncode=0,
            stdout=oversized_stdout,
            stderr="",
        )

        orig_run = subprocess.run
        try:
            subprocess.run = lambda *args, **kwargs: mock_proc  # type: ignore[assignment]
            out = analyzer.analyze(input_data)
            assert out.status == PipelineStatus.FAILED
            assert len(out.errors) >= 1
            assert "failed parsing worker json output" in out.errors[0].lower()
        finally:
            subprocess.run = orig_run  # type: ignore[assignment]
