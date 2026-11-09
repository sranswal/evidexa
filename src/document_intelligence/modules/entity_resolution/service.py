"""Application service orchestrating deterministic cross-document entity resolution and human reviews."""

from __future__ import annotations

import hashlib
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
    MatchDecisionStatus,
    PipelineStatus,
    ResolvedEntityType,
)
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMention,
    EntityResolutionResult,
    EntityResolutionRunSummary,
    HumanMatchReview,
)
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.entity_match_repository import (
    EntityMatchRepository,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.storage.interface import (
    DocumentStorageProtocol,
)
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.entity_resolution.engine.resolver import (
    EntityResolutionEngine,
)
from document_intelligence.modules.entity_resolution.normalizers import (
    normalize_bank_account_reference,
    normalize_currency_amount,
    normalize_invoice_reference,
    normalize_organization_name,
    normalize_person_name,
    normalize_tax_identifier,
)
from document_intelligence.modules.understanding.service import (
    DocumentUnderstandingService,
)

logger = logging.getLogger(__name__)


FIELD_TO_ENTITY_TYPE: dict[str, ResolvedEntityType] = {
    "vendor_name": ResolvedEntityType.ORGANIZATION,
    "merchant_name": ResolvedEntityType.ORGANIZATION,
    "company_name": ResolvedEntityType.ORGANIZATION,
    "bank_name": ResolvedEntityType.ORGANIZATION,
    "customer_name": ResolvedEntityType.PERSON,
    "account_holder_name": ResolvedEntityType.PERSON,
    "employee_name": ResolvedEntityType.PERSON,
    "tax_id": ResolvedEntityType.TAX_IDENTIFIER,
    "tax_identifier": ResolvedEntityType.TAX_IDENTIFIER,
    "ein": ResolvedEntityType.TAX_IDENTIFIER,
    "vat_number": ResolvedEntityType.TAX_IDENTIFIER,
    "pan": ResolvedEntityType.TAX_IDENTIFIER,
    "gstin": ResolvedEntityType.TAX_IDENTIFIER,
    "invoice_number": ResolvedEntityType.INVOICE_REFERENCE,
    "receipt_number": ResolvedEntityType.INVOICE_REFERENCE,
    "bill_number": ResolvedEntityType.INVOICE_REFERENCE,
    "account_number": ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
    "bank_account": ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
    "iban": ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
    "total_amount": ResolvedEntityType.CURRENCY_AMOUNT,
    "subtotal": ResolvedEntityType.CURRENCY_AMOUNT,
    "tax_amount": ResolvedEntityType.CURRENCY_AMOUNT,
    "net_amount": ResolvedEntityType.CURRENCY_AMOUNT,
    "transaction_id": ResolvedEntityType.TRANSACTION_REFERENCE,
    "reference_number": ResolvedEntityType.TRANSACTION_REFERENCE,
}


class EntityResolutionService:
    """Manages cross-document entity extraction, deterministic matching, and human review."""

    def __init__(
        self,
        case_service: CaseService,
        document_repo: DocumentRepository,
        run_repo: ProcessingRunRepository,
        match_repo: EntityMatchRepository,
        storage: DocumentStorageProtocol,
        audit_service: AuditLedgerService,
        understanding_service: DocumentUnderstandingService | None = None,
        engine: EntityResolutionEngine | None = None,
    ) -> None:
        self.case_service = case_service
        self.document_repo = document_repo
        self.run_repo = run_repo
        self.match_repo = match_repo
        self.storage = storage
        self.audit_service = audit_service
        self.understanding_service = understanding_service
        self.engine = engine or EntityResolutionEngine()

    def _ensure_case_writable(self, case_id: str) -> None:
        case = self.case_service.get_case(case_id)
        if case.status == CaseStatus.ARCHIVED:
            raise ValidationException(
                f"Cannot execute operations on archived case '{case.id}'.",
                details={"case_id": case.id, "status": case.status},
            )

    def _read_artifact(
        self, case_id: str, run_id: str, filename: str, expected_sha256: str | None = None
    ) -> bytes:
        artifact_key = f"{case_id}/entity-resolution/{run_id}/{filename}"
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

    def harvest_mentions_from_extractions(self, case_id: str) -> list[EntityMention]:
        """Harvest entity mentions from all completed structured extractions across documents in a case."""
        self._ensure_case_writable(case_id)
        docs, _ = self.document_repo.list_by_case(case_id=case_id)

        mentions: list[EntityMention] = []

        if not self.understanding_service:
            return mentions

        for doc in docs:
            try:
                extraction = self.understanding_service.get_latest_extraction(
                    case_id=case_id, document_id=doc.id
                )
            except NotFoundException:
                continue

            doc_currency = None
            if "currency" in extraction.fields and extraction.fields["currency"].normalized_value:
                doc_currency = str(extraction.fields["currency"].normalized_value)

            doc_tax_id = None
            if "tax_id" in extraction.fields and extraction.fields["tax_id"].normalized_value:
                doc_tax_id = str(extraction.fields["tax_id"].normalized_value)

            doc_inv_num = None
            if (
                "invoice_number" in extraction.fields
                and extraction.fields["invoice_number"].normalized_value
            ):
                doc_inv_num = str(extraction.fields["invoice_number"].normalized_value)

            for field_key, field_val in extraction.fields.items():
                if field_key not in FIELD_TO_ENTITY_TYPE:
                    continue

                raw_str = field_val.raw_text or str(field_val.normalized_value or "")
                if not raw_str or raw_str.strip() == "":
                    continue

                etype = FIELD_TO_ENTITY_TYPE[field_key]
                norm_val: str = ""
                base_name: str | None = None
                legal_suffix: str | None = None
                numeric_amt = None
                curr_code = doc_currency
                jurisdiction = None
                id_type = None

                if etype == ResolvedEntityType.ORGANIZATION:
                    norm_val, base_name, legal_suffix = normalize_organization_name(raw_str)
                elif etype == ResolvedEntityType.PERSON:
                    norm_val, base_name, _ = normalize_person_name(raw_str)
                elif etype == ResolvedEntityType.TAX_IDENTIFIER:
                    norm_val, jurisdiction, id_type, _ = normalize_tax_identifier(raw_str)
                elif etype in (
                    ResolvedEntityType.INVOICE_REFERENCE,
                    ResolvedEntityType.TRANSACTION_REFERENCE,
                ):
                    norm_val = normalize_invoice_reference(raw_str)
                elif etype == ResolvedEntityType.BANK_ACCOUNT_REFERENCE:
                    norm_val = normalize_bank_account_reference(raw_str)
                elif etype == ResolvedEntityType.CURRENCY_AMOUNT:
                    amt_input = (
                        field_val.normalized_value
                        if field_val.normalized_value is not None
                        else raw_str
                    )
                    norm_val, numeric_amt, curr_code = normalize_currency_amount(
                        amt_input, doc_currency
                    )

                # Ensure sensitive values are not stored unmasked in original_value
                orig_val = (
                    norm_val if etype == ResolvedEntityType.BANK_ACCOUNT_REFERENCE else raw_str
                )

                mention = EntityMention(
                    case_id=case_id,
                    document_id=doc.id,
                    page_number=field_val.source_page_number,
                    processing_run_id=extraction.processing_run_id,
                    field_key=field_key,
                    entity_type=etype,
                    original_value=orig_val,
                    normalized_value=norm_val,
                    numeric_amount=numeric_amt,
                    currency_code=curr_code,
                    jurisdiction=jurisdiction,
                    identifier_type=id_type,
                    legal_suffix=legal_suffix,
                    base_name=base_name,
                    supporting_evidence_node_ids=[field_val.evidence_node_id]
                    if field_val.evidence_node_id
                    else [],
                    bounding_boxes=field_val.source_bounding_boxes,
                    extraction_method=field_val.extraction_method,
                    schema_version=extraction.schema_id,
                    metadata={
                        "document_filename": doc.original_filename,
                        "tax_id": doc_tax_id,
                        "invoice_number": doc_inv_num,
                    },
                )
                mentions.append(mention)

        return mentions

    def resolve_case_entities(
        self,
        case_id: str,
        provided_mentions: list[EntityMention] | None = None,
        options: dict[str, Any] | None = None,
    ) -> EntityResolutionResult:
        """Execute deterministic entity resolution across all documents within a single case."""
        self._ensure_case_writable(case_id)

        mentions = (
            provided_mentions
            if provided_mentions is not None
            else self.harvest_mentions_from_extractions(case_id)
        )

        # Create ProcessingRun
        run = ProcessingRun(
            case_id=case_id,
            document_ids=sorted({m.document_id for m in mentions}),
            pipeline_name="cross-document-entity-resolution",
            pipeline_version="1.0.0",
            status=PipelineStatus.RUNNING,
        )
        self.run_repo.save(run)

        try:
            result = self.engine.resolve_entities(
                case_id=case_id,
                mentions=mentions,
                run_id=run.id,
                options=options,
            )

            # Persist candidate matches to relational store
            self.match_repo.save_matches(result.candidate_matches)

            # Persist complete JSON artifact
            art_data = result.model_dump_json(indent=2).encode("utf-8")
            art_name = f"entity_resolution_{run.id}.json"
            key, sha256 = self.storage.store_artifact(
                case_id=case_id,
                document_id="entity-resolution",
                processing_run_id=run.id,
                artifact_filename=art_name,
                data=art_data,
            )
            result.storage_artifact_key = key
            result.storage_artifact_sha256 = sha256

            # Mark run succeeded
            run.mark_succeeded()
            self.run_repo.save(run)

            # Audit event
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.ENTITIES_RESOLVED,
                entity_type=EntityType.PROCESSING_RUN,
                entity_id=run.id,
                actor_id="system",
                payload={
                    "total_mentions": len(mentions),
                    "candidate_matches_count": len(result.candidate_matches),
                    "resolved_entities_count": len(result.resolved_entities),
                    "processing_run_id": run.id,
                },
            )

            return result

        except Exception as exc:
            logger.exception("Entity resolution failed")
            run.mark_failed(error_code="RESOLUTION_FAILED", error_message=str(exc))
            self.run_repo.save(run)
            raise

    def get_run_result(
        self, case_id: str, run_id: str, expected_sha256: str | None = None
    ) -> EntityResolutionResult:
        """Retrieve full entity resolution result for a specific run from storage."""
        self.case_service.get_case(case_id)
        run = self.run_repo.get_by_id(run_id)
        if not run or run.case_id != case_id:
            raise NotFoundException(
                f"Entity resolution run '{run_id}' not found in case '{case_id}'."
            )

        filename = f"entity_resolution_{run_id}.json"
        raw_bytes = self._read_artifact(
            case_id=case_id, run_id=run_id, filename=filename, expected_sha256=expected_sha256
        )
        return EntityResolutionResult.model_validate_json(raw_bytes.decode("utf-8"))

    def get_latest_run_result(
        self, case_id: str, expected_sha256: str | None = None
    ) -> EntityResolutionResult:
        """Retrieve latest successful entity resolution result for a case."""
        self.case_service.get_case(case_id)
        runs, _ = self.run_repo.list_by_case(case_id=case_id)
        res_runs = [
            r
            for r in runs
            if r.status == PipelineStatus.SUCCEEDED
            and "entity-resolution" in r.pipeline_name.lower()
        ]
        if not res_runs:
            raise NotFoundException(f"No entity resolution results found for case '{case_id}'.")

        latest_run = sorted(res_runs, key=lambda r: r.started_at, reverse=True)[0]
        return self.get_run_result(
            case_id=case_id, run_id=latest_run.id, expected_sha256=expected_sha256
        )

    def list_resolution_runs(self, case_id: str) -> list[EntityResolutionRunSummary]:
        """List all entity resolution runs for a case."""
        self.case_service.get_case(case_id)
        runs, _ = self.run_repo.list_by_case(case_id=case_id)
        res_runs = [r for r in runs if "entity-resolution" in r.pipeline_name.lower()]

        summaries: list[EntityResolutionRunSummary] = []
        for r in res_runs:
            summaries.append(
                EntityResolutionRunSummary(
                    run_id=r.id,
                    case_id=case_id,
                    pipeline_name=r.pipeline_name,
                    pipeline_version=r.pipeline_version,
                    status=r.status.value,
                    started_at=r.started_at,
                    completed_at=r.completed_at,
                )
            )
        return summaries

    def list_matches(
        self,
        case_id: str,
        entity_type: str | None = None,
        classification: str | None = None,
        decision_status: str | None = None,
        review_status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[EntityCandidateMatch], int]:
        """List candidate matches with filtering and pagination."""
        self.case_service.get_case(case_id)
        return self.match_repo.list_matches(
            case_id=case_id,
            entity_type=entity_type,
            classification=classification,
            decision_status=decision_status,
            review_status=review_status,
            skip=skip,
            limit=limit,
        )

    def get_match(self, case_id: str, match_id: str) -> EntityCandidateMatch:
        """Get single match by ID with evidence and review history."""
        self.case_service.get_case(case_id)
        match = self.match_repo.get_match_by_id(case_id=case_id, match_id=match_id)
        if not match:
            raise NotFoundException(f"Match '{match_id}' not found in case '{case_id}'.")
        return match

    def submit_match_review(
        self,
        case_id: str,
        match_id: str,
        decision: str,
        reason: str,
        reviewer_id: str,
    ) -> EntityCandidateMatch:
        """Apply a human review decision to a candidate match."""
        self._ensure_case_writable(case_id)
        match = self.get_match(case_id, match_id)

        from document_intelligence.domain.enums import EntityReviewAction

        try:
            review_action = EntityReviewAction(decision.upper())
        except ValueError as exc:
            raise ValidationException(
                f"Invalid review decision '{decision}'. Must be one of: {[a.value for a in EntityReviewAction]}"
            ) from exc

        if review_action == EntityReviewAction.CONFIRM_MATCH:
            new_decision_status = MatchDecisionStatus.CONFIRMED
        elif review_action == EntityReviewAction.REJECT_MATCH:
            new_decision_status = MatchDecisionStatus.REJECTED
        else:
            new_decision_status = MatchDecisionStatus.AMBIGUOUS

        review = HumanMatchReview(
            match_id=match_id,
            case_id=case_id,
            decision=review_action,
            reviewer_id=reviewer_id,
            reason=reason,
            previous_status=match.decision_status,
            new_status=new_decision_status,
        )

        self.match_repo.save_review(review)

        # Audit event
        self.audit_service.record_event(
            case_id=case_id,
            event_type=AuditEventType.ENTITY_MATCH_REVIEWED,
            entity_type=EntityType.ENTITY_MATCH,
            entity_id=match_id,
            actor_id=reviewer_id,
            payload={
                "match_id": match_id,
                "decision": review_action.value,
                "previous_status": match.decision_status.value,
                "new_status": new_decision_status.value,
                "reason": reason,
                "asserted_reviewer_id": reviewer_id,
            },
        )

        return self.get_match(case_id, match_id)

    def list_match_reviews(self, case_id: str, match_id: str) -> list[HumanMatchReview]:
        """Retrieve human review history for a candidate match."""
        self.case_service.get_case(case_id)
        # Ensure match exists
        self.get_match(case_id, match_id)
        return self.match_repo.list_reviews_for_match(case_id, match_id)
