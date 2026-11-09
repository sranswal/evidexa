"""Application service orchestrating deterministic cross-document relationship discovery, persistence, and human reviews."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from document_intelligence.core.exceptions import (
    NotFoundException,
    SecurityException,
    ValidationException,
)
from document_intelligence.domain.enums import (
    AuditEventType,
    CaseStatus,
    EntityType,
    PipelineStatus,
    RelationshipReviewAction,
    RelationshipStatus,
)
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMention,
    ResolvedEntity,
)
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipDetectionResult,
    RelationshipDetectionRun,
    RelationshipReviewRecord,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.entity_match_repository import (
    EntityMatchRepository,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.repositories.relationship_repository import (
    RelationshipRepository,
)
from document_intelligence.infrastructure.storage.interface import (
    DocumentStorageProtocol,
)
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.entity_resolution.service import (
    EntityResolutionService,
)
from document_intelligence.modules.relationship_detection.detectors.base import (
    DetectionContext,
)
from document_intelligence.modules.relationship_detection.engine import (
    RelationshipDetectionEngine,
)
from document_intelligence.modules.understanding.service import (
    DocumentUnderstandingService,
)

logger = logging.getLogger(__name__)


class RelationshipDetectionService:
    """Manages cross-document relationship discovery, provenance tracking, and human review."""

    def __init__(
        self,
        case_service: CaseService,
        document_repo: DocumentRepository,
        run_repo: ProcessingRunRepository,
        relationship_repo: RelationshipRepository,
        storage: DocumentStorageProtocol,
        audit_service: AuditLedgerService,
        entity_match_repo: EntityMatchRepository | None = None,
        entity_resolution_service: EntityResolutionService | None = None,
        understanding_service: DocumentUnderstandingService | None = None,
        engine: RelationshipDetectionEngine | None = None,
    ) -> None:
        self.case_service = case_service
        self.document_repo = document_repo
        self.run_repo = run_repo
        self.relationship_repo = relationship_repo
        self.storage = storage
        self.audit_service = audit_service
        self.entity_match_repo = entity_match_repo
        self.entity_resolution_service = entity_resolution_service
        self.understanding_service = understanding_service
        self.engine = engine or RelationshipDetectionEngine()

    def _ensure_case_writable(self, case_id: str) -> None:
        case = self.case_service.get_case(case_id)
        if case.status == CaseStatus.ARCHIVED:
            raise ValidationException(
                f"Cannot execute operations on archived case '{case.id}'.",
                details={"case_id": case.id, "status": case.status},
            )

    def _read_artifact(
        self,
        case_id: str,
        run_id: str,
        filename: str,
        expected_sha256: str | None = None,
    ) -> bytes:
        artifact_key = f"{case_id}/relationship-detection/{run_id}/{filename}"
        art_path = self.storage.get_artifact_path(artifact_key)
        if not art_path.exists():
            raise NotFoundException(f"Artifact not found at key '{artifact_key}'.")
        raw_bytes = art_path.read_bytes()
        if expected_sha256 is not None:
            actual = hashlib.sha256(raw_bytes).hexdigest().lower()
            if actual != expected_sha256.lower():
                raise SecurityException(
                    f"Artifact integrity violation: expected SHA-256 {expected_sha256}, got {actual}."
                )
        return raw_bytes

    def detect_relationships_for_case(
        self,
        case_id: str,
        synthetic_transactions: list[dict[str, Any]] | None = None,
        provided_fields_by_doc: dict[str, list[ExtractedFieldValue]] | None = None,
        provided_raw_texts: dict[str, str] | None = None,
        caller_id: str | None = None,
    ) -> RelationshipDetectionResult:
        """Execute deterministic relationship detection across documents, entities, and records in a case."""
        self._ensure_case_writable(case_id)
        docs, _ = self.document_repo.list_by_case(case_id=case_id)

        # Create ProcessingRun
        run = ProcessingRun(
            case_id=case_id,
            document_ids=[d.id for d in docs],
            pipeline_name="cross-document-relationship-detection",
            pipeline_version="1.0.0",
            status=PipelineStatus.RUNNING,
        )
        self.run_repo.save(run)

        try:
            # 1. Harvest extracted fields
            extracted_fields: dict[str, list[ExtractedFieldValue]] = {}
            if provided_fields_by_doc is not None:
                extracted_fields = provided_fields_by_doc
            elif self.understanding_service:
                for doc in docs:
                    try:
                        ext_res = self.understanding_service.get_latest_extraction(
                            case_id=case_id, document_id=doc.id
                        )
                        extracted_fields[doc.id] = list(ext_res.fields.values())
                    except NotFoundException:
                        continue

            # 2. Harvest raw document texts
            raw_texts: dict[str, str] = {}
            if provided_raw_texts is not None:
                raw_texts = provided_raw_texts
            elif self.understanding_service:
                for doc in docs:
                    try:
                        ocr_res = self.understanding_service._get_or_run_ocr(
                            case_id=case_id, document_id=doc.id
                        )
                        raw_texts[doc.id] = ocr_res.full_raw_text
                    except Exception:
                        pass

            # 3. Harvest candidate matches and entity mentions from entity resolution
            candidate_matches: list[EntityCandidateMatch] = []
            entity_mentions: list[EntityMention] = []
            resolved_entities: list[ResolvedEntity] = []

            if self.entity_match_repo:
                matches, _ = self.entity_match_repo.list_matches(case_id=case_id, limit=500)
                candidate_matches = matches

            if self.entity_resolution_service:
                try:
                    mentions = self.entity_resolution_service.harvest_mentions_from_extractions(
                        case_id
                    )
                    entity_mentions = mentions
                except Exception:
                    pass

            # Construct Detection Context
            context = DetectionContext(
                case_id=case_id,
                detection_run_id=run.id,
                documents=docs,
                extracted_fields_by_doc=extracted_fields,
                resolved_entities=resolved_entities,
                candidate_matches=candidate_matches,
                entity_mentions=entity_mentions,
                raw_document_texts=raw_texts,
                synthetic_transactions=synthetic_transactions or [],
            )

            # Execute Engine Detection
            result = self.engine.detect_relationships(context)

            # Persist detected relationships to database
            self.relationship_repo.save_relationships(result.relationships)

            # Persist JSON Artifact to Storage
            art_data = result.model_dump_json(indent=2).encode("utf-8")
            art_name = f"relationship_detection_{run.id}.json"
            key, sha256 = self.storage.store_artifact(
                case_id=case_id,
                document_id="relationship-detection",
                processing_run_id=run.id,
                artifact_filename=art_name,
                data=art_data,
            )
            result.storage_artifact_key = key
            result.storage_artifact_sha256 = sha256

            # Mark run succeeded
            run.mark_succeeded()
            self.run_repo.save(run)

            # Record Audit Event
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.RELATIONSHIPS_DETECTED,
                entity_type=EntityType.PROCESSING_RUN,
                entity_id=run.id,
                actor_id=caller_id or "system",
                payload={
                    "total_documents": len(docs),
                    "relationships_detected": len(result.relationships),
                    "summary_by_type": result.summary_by_type,
                    "summary_by_status": result.summary_by_status,
                    "processing_run_id": run.id,
                },
            )

            return result

        except Exception as exc:
            logger.exception("Relationship detection failed for case %s", case_id)
            run.mark_failed(error_code="RELATIONSHIP_DETECTION_FAILED", error_message=str(exc))
            self.run_repo.save(run)
            raise

    def get_run_result(
        self, case_id: str, run_id: str, expected_sha256: str | None = None
    ) -> RelationshipDetectionResult:
        """Retrieve full relationship detection result for a run from storage with integrity verification."""
        self.case_service.get_case(case_id)
        run = self.run_repo.get_by_id(run_id)
        if not run or run.case_id != case_id:
            raise NotFoundException(
                f"Relationship detection run '{run_id}' not found in case '{case_id}'."
            )

        filename = f"relationship_detection_{run_id}.json"
        raw_bytes = self._read_artifact(
            case_id=case_id,
            run_id=run_id,
            filename=filename,
            expected_sha256=expected_sha256,
        )

        data = json.loads(raw_bytes.decode("utf-8"))
        res = RelationshipDetectionResult(**data)
        res.storage_artifact_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        return res

    def get_latest_result(self, case_id: str) -> RelationshipDetectionResult:
        """Retrieve the latest relationship detection result for a case."""
        runs = self.list_runs(case_id)
        if not runs:
            raise NotFoundException(f"No relationship detection runs found for case '{case_id}'.")
        latest_run = runs[0]
        return self.get_run_result(case_id=case_id, run_id=latest_run.id)

    def list_runs(self, case_id: str) -> list[RelationshipDetectionRun]:
        """List historical relationship detection runs for a case."""
        self.case_service.get_case(case_id)
        all_runs, _ = self.run_repo.list_by_case(case_id=case_id)
        runs = [r for r in all_runs if r.pipeline_name == "cross-document-relationship-detection"]
        return [
            RelationshipDetectionRun(
                id=r.id,
                case_id=r.case_id,
                pipeline_name=r.pipeline_name,
                pipeline_version=r.pipeline_version,
                started_at=r.started_at,
                completed_at=r.completed_at,
                total_documents=len(r.document_ids),
                relationships_detected=0,
                storage_artifact_key=None,
                storage_artifact_sha256=r.snapshot_sha256,
            )
            for r in runs
        ]

    def get_relationship(self, case_id: str, relationship_id: str) -> DetectedRelationship:
        """Retrieve a specific detected relationship and its review history."""
        self.case_service.get_case(case_id)
        rel = self.relationship_repo.get_relationship_by_id(
            case_id=case_id, relationship_id=relationship_id
        )
        if not rel:
            raise NotFoundException(
                f"Relationship '{relationship_id}' not found in case '{case_id}'."
            )
        return rel

    def list_relationships(
        self,
        case_id: str,
        relationship_type: str | None = None,
        status: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[DetectedRelationship], int]:
        """List and paginate detected relationships for a case with multi-criteria filtering."""
        self.case_service.get_case(case_id)
        return self.relationship_repo.list_relationships(
            case_id=case_id,
            relationship_type=relationship_type,
            status=status,
            source_id=source_id,
            target_id=target_id,
            skip=skip,
            limit=limit,
        )

    def review_relationship(
        self,
        case_id: str,
        relationship_id: str,
        decision: RelationshipReviewAction,
        reviewer_id: str,
        reason: str,
    ) -> DetectedRelationship:
        """Record human investigator review decision on a relationship with full audit trail."""
        self._ensure_case_writable(case_id)
        rel = self.get_relationship(case_id=case_id, relationship_id=relationship_id)

        # Map review action to new status
        if decision == RelationshipReviewAction.CONFIRM_RELATIONSHIP:
            new_status = RelationshipStatus.CONFIRMED
        elif decision == RelationshipReviewAction.REJECT_RELATIONSHIP:
            new_status = RelationshipStatus.REJECTED
        else:
            new_status = RelationshipStatus.UNRESOLVED

        review = RelationshipReviewRecord(
            relationship_id=relationship_id,
            case_id=case_id,
            decision=decision,
            reviewer_id=reviewer_id,
            reason=reason,
            previous_status=rel.status,
            new_status=new_status,
        )

        self.relationship_repo.save_review(review)

        # Audit Event
        self.audit_service.record_event(
            case_id=case_id,
            event_type=AuditEventType.RELATIONSHIP_REVIEWED,
            entity_type=EntityType.RELATIONSHIP,
            entity_id=relationship_id,
            actor_id=reviewer_id,
            payload={
                "relationship_id": relationship_id,
                "decision": decision.value,
                "previous_status": rel.status.value,
                "new_status": new_status.value,
                "reason": reason,
            },
        )

        return self.get_relationship(case_id=case_id, relationship_id=relationship_id)

    def list_relationship_reviews(
        self, case_id: str, relationship_id: str
    ) -> list[RelationshipReviewRecord]:
        """List chronological review decisions for a relationship."""
        self.case_service.get_case(case_id)
        self.get_relationship(case_id=case_id, relationship_id=relationship_id)
        return self.relationship_repo.list_reviews_for_relationship(
            case_id=case_id, relationship_id=relationship_id
        )
