"""ForensicProcessingService orchestrating document analysis, provenance, and persistence."""

import hashlib
from pathlib import Path
from typing import Any

from document_intelligence.core.exceptions import (
    NotFoundException,
    SecurityException,
    StorageException,
    ValidationException,
)
from document_intelligence.domain.enums import (
    AuditEventType,
    CaseStatus,
    EntityType,
    PipelineStatus,
)
from document_intelligence.domain.identifiers import utc_now
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.document_repository import DocumentRepository
from document_intelligence.infrastructure.repositories.evidence_repository import EvidenceRepository
from document_intelligence.infrastructure.repositories.finding_repository import FindingRepository
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.forensics.application.result_normalizer import (
    ForensicResultNormalizer,
)
from document_intelligence.modules.forensics.interfaces.registry import (
    AnalyzerRegistry,
    default_registry,
)
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput


def _compute_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 digest of a file in 64 KB chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


class ForensicProcessingService:
    """Orchestrates forensic document analysis lifecycle with strict provenance guarantees."""

    def __init__(
        self,
        processing_run_repo: ProcessingRunRepository,
        evidence_repo: EvidenceRepository,
        finding_repo: FindingRepository,
        document_repo: DocumentRepository,
        case_repo: CaseRepository,
        audit_service: AuditLedgerService,
        storage: DocumentStorageProtocol,
        registry: AnalyzerRegistry | None = None,
        normalizer: ForensicResultNormalizer | None = None,
    ) -> None:
        self.processing_run_repo = processing_run_repo
        self.evidence_repo = evidence_repo
        self.finding_repo = finding_repo
        self.document_repo = document_repo
        self.case_repo = case_repo
        self.audit_service = audit_service
        self.storage = storage
        self.registry = registry or default_registry
        self.normalizer = normalizer or ForensicResultNormalizer()

    def analyze_document(
        self,
        case_id: str,
        document_id: str,
        analyzer_id: str = "pdf-structural-analyzer",
        options: dict[str, Any] | None = None,
    ) -> tuple[ProcessingRun, list[ForensicFinding]]:
        """Run a registered forensic analyzer against a document with cryptographic verification.

        Guarantees:
        1. Pre-analysis SHA-256 verification against stored hash.
        2. Ephemeral analysis snapshot creation (analyzer never receives original file path).
        3. ProcessingRun lifecycle tracking (RUNNING -> SUCCEEDED / PARTIALLY_SUCCEEDED / FAILED).
        4. Post-analysis SHA-256 verification confirming document & snapshot immutability.
        5. Atomic persistence of evidence nodes, findings, and relational links.
        6. Full audit ledger trail (ANALYSIS_REQUESTED, PROCESSING_RUN_STARTED, PROCESSING_RUN_COMPLETED).
        """
        # 1. Validate case
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundException(f"Case '{case_id}' not found.", details={"case_id": case_id})
        if case.status == CaseStatus.ARCHIVED:
            raise ValidationException(
                f"Cannot initiate analysis on archived case '{case_id}'.",
                details={"case_id": case_id, "case_status": case.status.value},
            )

        # 2. Validate document
        doc = self.document_repo.get_by_id(document_id)
        if not doc:
            raise NotFoundException(
                f"Document '{document_id}' not found.",
                details={"document_id": document_id},
            )
        if doc.case_id != case_id:
            raise ValidationException(
                f"Document '{document_id}' does not belong to case '{case_id}'.",
                details={"document_id": document_id, "case_id": case_id},
            )

        # 3. Locate analyzer
        analyzer = self.registry.get(analyzer_id)
        if not analyzer:
            raise ValidationException(
                f"Forensic analyzer '{analyzer_id}' is not registered.",
                details={"analyzer_id": analyzer_id},
            )

        # Check media type compatibility
        if not analyzer.can_analyze(doc.media_type):
            raise ValidationException(
                f"Analyzer '{analyzer_id}' does not support media type '{doc.media_type}'.",
                details={"analyzer_id": analyzer_id, "media_type": doc.media_type},
            )

        # 4. Record audit event: ANALYSIS_REQUESTED
        self.audit_service.record_event(
            case_id=case_id,
            event_type=AuditEventType.ANALYSIS_REQUESTED,
            entity_type=EntityType.DOCUMENT,
            entity_id=document_id,
            payload={
                "analyzer_id": analyzer_id,
                "options": options or {},
            },
        )

        # 5. Resolve original file path & verify pre-analysis hash
        orig_file_path = self.storage.get_original_path(doc.storage_key)
        if not orig_file_path.exists() or not orig_file_path.is_file():
            raise StorageException(
                f"Document binary file missing at storage location: {doc.storage_key}",
                details={"storage_key": doc.storage_key},
            )

        pre_orig_hash = _compute_file_sha256(orig_file_path)
        if pre_orig_hash != doc.sha256.lower():
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.INTEGRITY_VERIFICATION_FAILED,
                entity_type=EntityType.DOCUMENT,
                entity_id=document_id,
                payload={
                    "expected_sha256": doc.sha256.lower(),
                    "actual_sha256": pre_orig_hash,
                    "stage": "pre_analysis_original_check",
                },
            )
            raise SecurityException(
                "Document integrity verification failed prior to analysis: SHA-256 hash mismatch.",
                details={
                    "expected_sha256": doc.sha256.lower(),
                    "actual_sha256": pre_orig_hash,
                    "document_id": document_id,
                },
            )

        # 6. Initialize ProcessingRun
        run = ProcessingRun(
            case_id=case_id,
            document_ids=[document_id],
            pipeline_name=analyzer.name,
            pipeline_version=analyzer.version,
            status=PipelineStatus.RUNNING,
            configuration_snapshot=options or {},
        )

        # 7. Create ephemeral analysis snapshot (parser never sees original path)
        snapshot_path, snapshot_sha256 = self.storage.create_analysis_snapshot(
            storage_key=doc.storage_key,
            processing_run_id=run.id,
        )

        if snapshot_sha256 != doc.sha256.lower():
            self.storage.cleanup_analysis_snapshot(snapshot_path)
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.INTEGRITY_VERIFICATION_FAILED,
                entity_type=EntityType.PROCESSING_RUN,
                entity_id=run.id,
                payload={
                    "expected_sha256": doc.sha256.lower(),
                    "snapshot_sha256": snapshot_sha256,
                    "stage": "snapshot_creation",
                },
            )
            raise SecurityException(
                "Integrity error: analysis snapshot hash does not match stored document hash.",
                details={
                    "expected_sha256": doc.sha256.lower(),
                    "snapshot_sha256": snapshot_sha256,
                },
            )

        run.snapshot_sha256 = snapshot_sha256
        self.processing_run_repo.save(run)

        # 8. Record audit event: PROCESSING_RUN_STARTED
        self.audit_service.record_event(
            case_id=case_id,
            event_type=AuditEventType.PROCESSING_RUN_STARTED,
            entity_type=EntityType.PROCESSING_RUN,
            entity_id=run.id,
            payload={
                "document_id": document_id,
                "analyzer_id": analyzer_id,
                "pipeline_name": analyzer.name,
                "pipeline_version": analyzer.version,
                "snapshot_sha256": snapshot_sha256,
                "options": options or {},
            },
        )

        # 9. Execute analyzer against ephemeral snapshot
        try:
            timeout_sec = float((options or {}).get("timeout_sec", 30.0))
            analyzer_input = AnalyzerInput(
                file_path=snapshot_path,
                declared_media_type=doc.media_type,
                detected_media_type=doc.media_type,
                document_sha256=doc.sha256,
                document_id=document_id,
                case_id=case_id,
                processing_run_id=run.id,
                options=options or {},
                timeout_seconds=timeout_sec,
            )

            try:
                output = analyzer.analyze(analyzer_input)
            except Exception as exc:
                run.mark_failed(error_code="ANALYSIS_EXECUTION_FAILED", error_message=str(exc))
                self.processing_run_repo.save(run)
                self.audit_service.record_event(
                    case_id=case_id,
                    event_type=AuditEventType.PROCESSING_RUN_COMPLETED,
                    entity_type=EntityType.PROCESSING_RUN,
                    entity_id=run.id,
                    payload={
                        "status": PipelineStatus.FAILED.value,
                        "error_code": "ANALYSIS_EXECUTION_FAILED",
                        "error_message": str(exc),
                    },
                )
                raise

            # 10. Post-analysis SHA-256 verifications
            # Immutability check 1: Snapshot file was not altered
            if snapshot_path.exists():
                post_snap_hash = _compute_file_sha256(snapshot_path)
                if post_snap_hash != snapshot_sha256:
                    run.mark_failed(
                        error_code="SNAPSHOT_IMMUTABILITY_VIOLATION",
                        error_message="Ephemeral snapshot was modified during analysis execution.",
                    )
                    self.processing_run_repo.save(run)
                    self.audit_service.record_event(
                        case_id=case_id,
                        event_type=AuditEventType.INTEGRITY_VERIFICATION_FAILED,
                        entity_type=EntityType.PROCESSING_RUN,
                        entity_id=run.id,
                        payload={
                            "expected_sha256": snapshot_sha256,
                            "actual_sha256": post_snap_hash,
                            "stage": "post_analysis_snapshot_check",
                        },
                    )
                    raise SecurityException(
                        "Critical integrity violation: ephemeral snapshot file hash changed during analysis.",
                        details={
                            "pre_analysis_sha256": snapshot_sha256,
                            "post_analysis_sha256": post_snap_hash,
                            "document_id": document_id,
                        },
                    )

            # Immutability check 2: Original file remained completely untouched
            post_orig_hash = _compute_file_sha256(orig_file_path)
            if post_orig_hash != pre_orig_hash:
                run.mark_failed(
                    error_code="ORIGINAL_IMMUTABILITY_VIOLATION",
                    error_message="Stored original file was modified during analysis execution.",
                )
                self.processing_run_repo.save(run)
                self.audit_service.record_event(
                    case_id=case_id,
                    event_type=AuditEventType.INTEGRITY_VERIFICATION_FAILED,
                    entity_type=EntityType.PROCESSING_RUN,
                    entity_id=run.id,
                    payload={
                        "expected_sha256": pre_orig_hash,
                        "actual_sha256": post_orig_hash,
                        "stage": "post_analysis_original_check",
                    },
                )
                raise SecurityException(
                    "Critical integrity violation: stored original file hash changed during analysis.",
                    details={
                        "pre_analysis_sha256": pre_orig_hash,
                        "post_analysis_sha256": post_orig_hash,
                        "document_id": document_id,
                    },
                )

            # 11. Normalize observations into domain entities
            evidence_nodes, findings, links = self.normalizer.normalize(
                output=output,
                case_id=case_id,
                document_id=document_id,
                processing_run_id=run.id,
            )

            # 12. Persist evidence nodes, findings, and relational links
            self.evidence_repo.save_bulk(evidence_nodes)
            self.finding_repo.save_bulk(findings, links)

            # 13. Update processing run status and resource metrics
            if output.status == PipelineStatus.FAILED:
                run.status = PipelineStatus.FAILED
                combined_errors = "; ".join(output.errors)
                if "encrypted" in combined_errors.lower() or "password" in combined_errors.lower():
                    run.error_code = "PDF_ENCRYPTED"
                elif "timeout" in combined_errors.lower() or "timed out" in combined_errors.lower():
                    run.error_code = "ANALYSIS_TIMEOUT"
                else:
                    run.error_code = "ANALYZER_REPORTED_FAILURE"
                run.error_message = combined_errors[:2000] if output.errors else "Analyzer failure"
                run.completed_at = utc_now()
            elif output.errors or output.status == PipelineStatus.PARTIALLY_SUCCEEDED:
                run.status = PipelineStatus.PARTIALLY_SUCCEEDED
                run.completed_at = utc_now()
            else:
                run.mark_succeeded()

            run.resource_metrics = {
                "duration_ms": output.execution_duration_ms,
                "observations_count": len(output.observations),
                "evidence_count": len(evidence_nodes),
                "findings_count": len(findings),
                "errors_count": len(output.errors),
            }
            self.processing_run_repo.save(run)

            # 14. Record audit event: PROCESSING_RUN_COMPLETED
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.PROCESSING_RUN_COMPLETED,
                entity_type=EntityType.PROCESSING_RUN,
                entity_id=run.id,
                payload={
                    "status": run.status.value,
                    "findings_count": len(findings),
                    "evidence_count": len(evidence_nodes),
                    "duration_ms": output.execution_duration_ms,
                    "errors": output.errors,
                },
            )

            return run, findings

        finally:
            self.storage.cleanup_analysis_snapshot(snapshot_path)

    def recover_stale_runs(self) -> int:
        """Identify runs abandoned in RUNNING state (e.g. server crash) and mark them FAILED.

        Guarantees:
        - Detects any ProcessingRun left in RUNNING status on server startup/recovery.
        - Transitions status to FAILED with error code RUN_INTERRUPTED.
        - Records PROCESSING_RUN_INTERRUPTED and PROCESSING_RUN_COMPLETED audit events.
        """
        stale_runs = self.processing_run_repo.list_by_status(PipelineStatus.RUNNING)
        recovered_count = 0

        for run in stale_runs:
            run.mark_failed(
                error_code="RUN_INTERRUPTED",
                error_message="Execution interrupted by unexpected server shutdown or restart.",
            )
            self.processing_run_repo.save(run)

            self.audit_service.record_event(
                case_id=run.case_id,
                event_type=AuditEventType.PROCESSING_RUN_INTERRUPTED,
                entity_type=EntityType.PROCESSING_RUN,
                entity_id=run.id,
                payload={
                    "status": PipelineStatus.FAILED.value,
                    "error_code": "RUN_INTERRUPTED",
                    "recovery_reason": "stale_run_cleanup_on_startup",
                },
            )

            self.audit_service.record_event(
                case_id=run.case_id,
                event_type=AuditEventType.PROCESSING_RUN_COMPLETED,
                entity_type=EntityType.PROCESSING_RUN,
                entity_id=run.id,
                payload={
                    "status": PipelineStatus.FAILED.value,
                    "error_code": "RUN_INTERRUPTED",
                    "error_message": "Execution interrupted by unexpected server shutdown or restart.",
                },
            )
            recovered_count += 1

        return recovered_count
