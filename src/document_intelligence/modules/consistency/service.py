"""Application service orchestrating cross-document consistency analysis, persistence, and human reviews."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from document_intelligence.core.exceptions import (
    NotFoundException,
    SecurityException,
    ValidationException,
)
from document_intelligence.domain.enums import (
    AuditEventType,
    CaseStatus,
    ConsistencyReviewAction,
    EntityType,
    FindingStatus,
    PipelineStatus,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.consistency import (
    ConsistencyAnalysisResult,
    ConsistencyFinding,
    ConsistencyReview,
)
from document_intelligence.domain.models.entity_resolution import ResolvedEntity
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.domain.models.relationship import DetectedRelationship
from document_intelligence.infrastructure.repositories.consistency_repository import (
    ConsistencyRepository,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.entity_match_repository import (
    EntityMatchRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
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
from document_intelligence.modules.consistency.context import ConsistencyContext
from document_intelligence.modules.consistency.engine import (
    ConsistencyAnalysisEngine,
    default_consistency_rule_registry,
)
from document_intelligence.modules.understanding.service import (
    DocumentUnderstandingService,
)

logger = logging.getLogger(__name__)


class ConsistencyAnalysisService:
    """Orchestrates cross-document deterministic consistency checks and human review decisions."""

    def __init__(
        self,
        case_service: CaseService,
        document_repo: DocumentRepository,
        run_repo: ProcessingRunRepository,
        consistency_repo: ConsistencyRepository,
        storage: DocumentStorageProtocol,
        audit_service: AuditLedgerService,
        understanding_service: DocumentUnderstandingService | None = None,
        entity_match_repo: EntityMatchRepository | None = None,
        relationship_repo: RelationshipRepository | None = None,
        evidence_repo: EvidenceRepository | None = None,
        engine: ConsistencyAnalysisEngine | None = None,
    ) -> None:
        self.case_service = case_service
        self.document_repo = document_repo
        self.run_repo = run_repo
        self.consistency_repo = consistency_repo
        self.storage = storage
        self.audit_service = audit_service
        self.understanding_service = understanding_service
        self.entity_match_repo = entity_match_repo
        self.relationship_repo = relationship_repo
        self.evidence_repo = evidence_repo
        self.engine = engine or ConsistencyAnalysisEngine(default_consistency_rule_registry)

    def _ensure_case_writable(self, case_id: str) -> None:
        case = self.case_service.get_case(case_id)
        if case.status == CaseStatus.ARCHIVED:
            raise SecurityException(f"Cannot execute operations on archived case '{case.id}'.")

    def analyze_case(
        self,
        case_id: str,
        document_ids: list[str] | None = None,
        rule_ids: list[str] | None = None,
        monetary_tolerance: Decimal | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> ConsistencyAnalysisResult:
        """Execute deterministic cross-document consistency rules across documents in a case."""
        self._ensure_case_writable(case_id)

        # Resolve documents
        all_case_docs, _ = self.document_repo.list_by_case(case_id=case_id)
        if document_ids:
            target_ids = set(document_ids)
            docs = [d for d in all_case_docs if d.id in target_ids]
            if len(docs) != len(target_ids):
                found_ids = {d.id for d in docs}
                missing = target_ids - found_ids
                raise NotFoundException(f"Documents not found in case: {sorted(missing)}")
        else:
            docs = all_case_docs

        if not docs:
            raise ValidationException(
                "Case has no uploaded documents available for consistency analysis."
            )

        started_at = utc_now()

        # Create processing run record
        run = ProcessingRun(
            case_id=case_id,
            document_ids=[d.id for d in docs],
            pipeline_name="cross_document_consistency_engine",
            pipeline_version="1.0.0",
            status=PipelineStatus.RUNNING,
            started_at=started_at,
            configuration_snapshot={
                "rule_ids": rule_ids or "ALL_REGISTERED",
                "monetary_tolerance": str(monetary_tolerance or Decimal("0.00")),
                "parameters": parameters or {},
            },
        )
        self.run_repo.save(run)

        # Gather extracted fields and evidence nodes
        extracted_fields_by_doc: dict[str, list[ExtractedFieldValue]] = {}
        evidence_nodes_by_doc: dict[str, list[EvidenceNode]] = {}
        raw_texts: dict[str, str] = {}

        for doc in docs:
            # 1. Extracted fields
            if self.understanding_service:
                try:
                    ext_res = self.understanding_service.get_latest_extraction(
                        case_id=case_id, document_id=doc.id
                    )
                    if ext_res and ext_res.fields:
                        extracted_fields_by_doc[doc.id] = list(ext_res.fields.values())
                except NotFoundException:
                    pass
                except Exception as e:
                    logger.debug("No extracted fields for doc %s: %s", doc.id, e)

            # 2. Evidence nodes
            if self.evidence_repo:
                try:
                    nodes, _ = self.evidence_repo.list_by_case(case_id=case_id, document_id=doc.id)
                    evidence_nodes_by_doc[doc.id] = nodes
                except Exception as e:
                    logger.debug("Could not fetch evidence nodes for doc %s: %s", doc.id, e)

            # 3. Raw text
            if self.understanding_service:
                try:
                    ocr_res = self.understanding_service._get_or_run_ocr(
                        case_id=case_id, document_id=doc.id
                    )
                    raw_texts[doc.id] = ocr_res.full_raw_text
                except Exception:
                    pass

        # Resolved entities and relationships (signals)
        resolved_entities: list[ResolvedEntity] = []
        detected_relationships: list[DetectedRelationship] = []

        if self.relationship_repo:
            try:
                rels, _ = self.relationship_repo.list_relationships(case_id=case_id, limit=500)
                detected_relationships = rels
            except Exception as e:
                logger.debug("Could not fetch relationships: %s", e)

        # Build context
        context = ConsistencyContext(
            case_id=case_id,
            analysis_run_id=run.id,
            documents=docs,
            extracted_fields_by_doc=extracted_fields_by_doc,
            evidence_nodes_by_doc=evidence_nodes_by_doc,
            resolved_entities=resolved_entities,
            detected_relationships=detected_relationships,
            raw_document_texts=raw_texts,
            synthetic_transactions=parameters.get("transactions", []) if parameters else [],
            monetary_tolerance=monetary_tolerance or Decimal("0.00"),
            parameters=parameters or {},
        )

        # Execute analysis engine
        findings = self.engine.analyze(context, rule_ids=rule_ids)

        # Persist findings
        self.consistency_repo.save_findings(findings)

        # Calculate outcomes summary
        outcomes_summary: dict[str, int] = {}
        for f in findings:
            outcomes_summary[f.outcome.value] = outcomes_summary.get(f.outcome.value, 0) + 1

        # Store run artifact summary in case storage hierarchy
        completed_at = utc_now()
        duration_ms = (completed_at - started_at).total_seconds() * 1000.0

        run_result = ConsistencyAnalysisResult(
            case_id=case_id,
            analysis_run_id=run.id,
            status=PipelineStatus.SUCCEEDED,
            findings=findings,
            total_findings=len(findings),
            outcomes_summary=outcomes_summary,
            rules_applied=rule_ids
            or [r.rule_id for r in default_consistency_rule_registry.list_rules()],
            duration_ms=duration_ms,
        )

        art_data = run_result.model_dump_json(indent=2).encode("utf-8")
        art_name = f"consistency_analysis_{run.id}.json"
        artifact_key, artifact_sha256 = self.storage.store_artifact(
            case_id=case_id,
            document_id="consistency",
            processing_run_id=run.id,
            artifact_filename=art_name,
            data=art_data,
        )

        run_result.storage_artifact_key = artifact_key
        run_result.storage_artifact_sha256 = artifact_sha256

        # Update processing run status to SUCCEEDED
        run.mark_succeeded()
        run.snapshot_sha256 = artifact_sha256
        self.run_repo.save(run)

        # Record audit event: analysis completed
        self.audit_service.record_event(
            case_id=case_id,
            event_type=AuditEventType.CONSISTENCY_ANALYSIS_COMPLETED,
            entity_type=EntityType.PROCESSING_RUN,
            entity_id=run.id,
            actor_id="system",
            payload={
                "findings_count": len(findings),
                "outcomes_summary": outcomes_summary,
                "artifact_key": artifact_key,
                "artifact_sha256": artifact_sha256,
            },
        )

        return run_result

    def list_findings(
        self,
        case_id: str,
        run_id: str | None = None,
        rule_id: str | None = None,
        outcome: str | None = None,
        status: str | None = None,
        document_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConsistencyFinding]:
        """List consistency findings for a case with optional filters."""
        self.case_service.get_case(case_id)
        return self.consistency_repo.list_findings(
            case_id=case_id,
            run_id=run_id,
            rule_id=rule_id,
            outcome=outcome,
            status=status,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )

    def get_finding_or_404(self, case_id: str, finding_id: str) -> ConsistencyFinding:
        """Retrieve an individual consistency finding by ID within a case."""
        self.case_service.get_case(case_id)
        finding = self.consistency_repo.get_finding(finding_id, case_id)
        if not finding:
            raise NotFoundException(
                f"Consistency finding '{finding_id}' not found in case '{case_id}'."
            )
        return finding

    def review_finding(
        self,
        case_id: str,
        finding_id: str,
        decision: ConsistencyReviewAction,
        reviewer_id: str,
        reason: str,
    ) -> ConsistencyFinding:
        """Apply human reviewer decision to a consistency finding with append-only audit trail."""
        self._ensure_case_writable(case_id)

        if not reviewer_id or not reviewer_id.strip():
            raise ValidationException("Reviewer identifier is required.")
        if not reason or not reason.strip():
            raise ValidationException("Review justification comment is required.")

        finding = self.get_finding_or_404(case_id, finding_id)

        # Map review action to new finding status
        action_status_map = {
            ConsistencyReviewAction.CONFIRM_INCONSISTENCY: FindingStatus.CONFIRMED_OBSERVATION,
            ConsistencyReviewAction.DISMISS: FindingStatus.DISMISSED,
            ConsistencyReviewAction.MARK_INSUFFICIENT_EVIDENCE: FindingStatus.RESOLVED,
            ConsistencyReviewAction.REQUEST_MORE_EVIDENCE: FindingStatus.NEEDS_REVIEW,
        }

        previous_status = finding.status.value
        new_status = action_status_map[decision]

        review = ConsistencyReview(
            id=generate_id(),
            finding_id=finding_id,
            case_id=case_id,
            decision=decision,
            reviewer_id=reviewer_id.strip(),
            reason=reason.strip(),
            reviewed_at=utc_now(),
            previous_status=previous_status,
            new_status=new_status.value,
        )

        # Persist review
        self.consistency_repo.save_review(review)

        # Update finding
        finding.status = new_status
        finding.review_status = decision.value
        finding.is_human_reviewed = True
        finding.updated_at = utc_now()
        finding.review_history.append(review)

        self.consistency_repo.save_finding(finding)

        # Audit event
        self.audit_service.record_event(
            case_id=case_id,
            event_type=AuditEventType.CONSISTENCY_FINDING_REVIEWED,
            entity_type=EntityType.CONSISTENCY_REVIEW,
            entity_id=review.id,
            actor_id=reviewer_id,
            payload={
                "finding_id": finding_id,
                "decision": decision.value,
                "previous_status": previous_status,
                "new_status": new_status.value,
                "reason": reason,
            },
        )

        return finding

    def get_review_history(self, case_id: str, finding_id: str) -> list[ConsistencyReview]:
        """Retrieve chronological human review history for a finding."""
        self.get_finding_or_404(case_id, finding_id)
        return self.consistency_repo.list_reviews_for_finding(finding_id, case_id)

    def get_runs_for_case(self, case_id: str) -> list[ProcessingRun]:
        """List consistency analysis runs for a case."""
        self.case_service.get_case(case_id)
        runs, _ = self.run_repo.list_by_case(case_id=case_id)
        return [r for r in runs if r.pipeline_name == "cross_document_consistency_engine"]

    def get_run(self, case_id: str, run_id: str) -> ProcessingRun:
        """Retrieve a specific consistency run."""
        self.case_service.get_case(case_id)
        run = self.run_repo.get_by_id(run_id)
        if not run or run.case_id != case_id:
            raise NotFoundException(f"Processing run '{run_id}' not found in case '{case_id}'.")
        return run
