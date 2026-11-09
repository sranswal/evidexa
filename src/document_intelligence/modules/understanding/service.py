"""Application service coordinating document classification and structured field extraction."""

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
    CoordinateSystem,
    DocumentClass,
    DocumentType,
    EntityType,
    EvidenceType,
    FieldDataType,
    FieldValidationStatus,
    PipelineStatus,
)
from document_intelligence.domain.models.classification import (
    ClassificationOverride,
    DocumentClassificationResult,
)
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.extraction import (
    DocumentExtractionResult,
    ExtractionSchema,
)
from document_intelligence.domain.models.ocr import ExtractedDocumentText
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.forensics.application.processing_service import (
    ForensicProcessingService,
)
from document_intelligence.modules.understanding.classification.classifier import (
    RuleBasedDocumentClassifier,
)
from document_intelligence.modules.understanding.extraction.engine import (
    StructuredFieldExtractor,
)
from document_intelligence.modules.understanding.extraction.schemas.registry import (
    SchemaRegistry,
    default_schema_registry,
)

logger = logging.getLogger(__name__)


class DocumentUnderstandingService:
    """Service orchestrating classification, field extraction, and Evidence Graph indexing."""

    def __init__(
        self,
        case_service: CaseService,
        document_repo: DocumentRepository,
        run_repo: ProcessingRunRepository,
        evidence_repo: EvidenceRepository,
        audit_service: AuditLedgerService,
        storage: DocumentStorageProtocol | None = None,
        forensic_processing: ForensicProcessingService | None = None,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self.case_service = case_service
        self.document_repo = document_repo
        self.run_repo = run_repo
        self.evidence_repo = evidence_repo
        self.audit_service = audit_service
        self.storage = storage or FilesystemDocumentStorage()
        self.forensic_processing = forensic_processing
        self.schema_registry = schema_registry or default_schema_registry
        self.classifier = RuleBasedDocumentClassifier()
        self.extractor = StructuredFieldExtractor()

    def _get_validated_doc_and_case(self, case_id: str, document_id: str) -> tuple[Any, Any]:
        """Verify case and document exist and are properly scoped."""
        case = self.case_service.get_case(case_id)
        doc = self.document_repo.get_by_id(document_id)
        if not doc or doc.case_id != case.id:
            raise NotFoundException(
                f"Document '{document_id}' not found in case '{case_id}'.",
                details={"case_id": case_id, "document_id": document_id},
            )
        return case, doc

    def _ensure_case_not_archived(self, case: Any) -> None:
        """Reject write operations on archived cases."""
        if case.status == CaseStatus.ARCHIVED:
            raise ValidationException(
                f"Cannot modify archived case '{case.id}'.",
                details={"case_id": case.id, "status": case.status},
            )

    def _read_artifact(
        self,
        case_id: str,
        document_id: str,
        processing_run_id: str,
        artifact_filename: str,
        expected_sha256: str | None = None,
    ) -> bytes:
        """Resolve and read a stored JSON/bytes artifact with optional SHA-256 verification."""
        artifact_key = f"{case_id}/{document_id}/{processing_run_id}/{artifact_filename}"
        art_path = self.storage.get_artifact_path(artifact_key)
        if not art_path.exists():
            raise NotFoundException(f"Artifact not found at key '{artifact_key}'.")
        raw_bytes = art_path.read_bytes()
        if expected_sha256 is not None:
            actual_sha256 = hashlib.sha256(raw_bytes).hexdigest().lower()
            if actual_sha256 != expected_sha256.lower():
                raise SecurityException(
                    f"Artifact integrity violation: expected SHA-256 {expected_sha256}, got {actual_sha256}."
                )
        return raw_bytes

    def _get_or_run_ocr(self, case_id: str, document_id: str) -> ExtractedDocumentText:
        """Retrieve completed OCR text artifact or execute default OCR run."""
        runs, _ = self.run_repo.list_by_case(case_id=case_id, document_id=document_id)
        ocr_runs = [
            r
            for r in runs
            if r.status in (PipelineStatus.SUCCEEDED, PipelineStatus.PARTIALLY_SUCCEEDED)
            and "ocr" in r.pipeline_name.lower()
        ]

        if ocr_runs:
            latest_run = sorted(ocr_runs, key=lambda r: r.started_at, reverse=True)[0]
            filename = f"ocr_{latest_run.id}_extracted.json"
            try:
                raw_bytes = self._read_artifact(
                    case_id=case_id,
                    document_id=document_id,
                    processing_run_id=latest_run.id,
                    artifact_filename=filename,
                )
                return ExtractedDocumentText.model_validate_json(raw_bytes.decode("utf-8"))
            except Exception as exc:
                logger.warning(f"Could not load existing OCR artifact: {exc}")

        # If no OCR run exists, trigger hybrid OCR if forensic_processing service is available
        if self.forensic_processing is not None:
            run, _ = self.forensic_processing.analyze_document(
                case_id=case_id,
                document_id=document_id,
                analyzer_id="hybrid-ocr-pipeline",
            )
            filename = f"ocr_{run.id}_extracted.json"
            raw_bytes = self._read_artifact(
                case_id=case_id,
                document_id=document_id,
                processing_run_id=run.id,
                artifact_filename=filename,
            )
            return ExtractedDocumentText.model_validate_json(raw_bytes.decode("utf-8"))

        raise ValidationException(
            f"No OCR extraction artifact found for document '{document_id}'. Run OCR first."
        )

    def classify_document(
        self,
        case_id: str,
        document_id: str,
        options: dict[str, Any] | None = None,
    ) -> DocumentClassificationResult:
        """Classify document and all constituent pages based on extracted text."""
        case, doc = self._get_validated_doc_and_case(case_id, document_id)
        self._ensure_case_not_archived(case)

        extracted_doc = self._get_or_run_ocr(case_id, document_id)

        # Create processing run
        run = ProcessingRun(
            case_id=case_id,
            document_ids=[document_id],
            pipeline_name="document-classification",
            pipeline_version=self.classifier.classifier_version,
            status=PipelineStatus.RUNNING,
        )
        self.run_repo.save(run)

        try:
            result = self.classifier.classify_document(extracted_doc)
            result.processing_run_id = run.id

            # Persist artifact
            art_data = result.model_dump_json(indent=2).encode("utf-8")
            art_name = f"classification_{run.id}.json"
            key, sha256 = self.storage.store_artifact(
                case_id=case_id,
                document_id=document_id,
                processing_run_id=run.id,
                artifact_filename=art_name,
                data=art_data,
            )
            result.storage_artifact_key = key
            result.storage_artifact_sha256 = sha256

            # Update document type if currently UNKNOWN
            if result.effective_class != DocumentClass.UNKNOWN:
                try:
                    doc.document_type = DocumentType(result.effective_class.value)
                    self.document_repo.save(doc)
                except (ValueError, KeyError):
                    pass

            # Mark run succeeded
            run.mark_succeeded()
            self.run_repo.save(run)

            # Record audit event
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.DOCUMENT_CLASSIFIED,
                entity_type=EntityType.DOCUMENT,
                entity_id=document_id,
                actor_id="system",
                payload={
                    "predicted_class": result.predicted_class.value,
                    "effective_class": result.effective_class.value,
                    "ranking_score": result.ranking_score,
                    "processing_run_id": run.id,
                },
            )

            return result

        except Exception as exc:
            logger.exception("Document classification failed")
            run.mark_failed(error_code="CLASSIFICATION_FAILED", error_message=str(exc))
            self.run_repo.save(run)
            raise

    def get_latest_classification(
        self, case_id: str, document_id: str, expected_sha256: str | None = None
    ) -> DocumentClassificationResult:
        """Retrieve latest document classification result."""
        self._get_validated_doc_and_case(case_id, document_id)

        runs, _ = self.run_repo.list_by_case(case_id=case_id, document_id=document_id)
        class_runs = [
            r
            for r in runs
            if r.status == PipelineStatus.SUCCEEDED and "classification" in r.pipeline_name.lower()
        ]
        if not class_runs:
            raise NotFoundException(
                f"No classification results found for document '{document_id}'."
            )

        latest_run = sorted(class_runs, key=lambda r: r.started_at, reverse=True)[0]
        filename = f"classification_{latest_run.id}.json"
        raw_bytes = self._read_artifact(
            case_id=case_id,
            document_id=document_id,
            processing_run_id=latest_run.id,
            artifact_filename=filename,
            expected_sha256=expected_sha256,
        )
        return DocumentClassificationResult.model_validate_json(raw_bytes.decode("utf-8"))

    def override_classification(
        self,
        case_id: str,
        document_id: str,
        overridden_class: DocumentClass,
        overridden_by: str,
        reason: str,
    ) -> DocumentClassificationResult:
        """Record human review override of document classification without deleting original machine score."""
        case, doc = self._get_validated_doc_and_case(case_id, document_id)
        self._ensure_case_not_archived(case)

        current_result = self.get_latest_classification(case_id, document_id)

        override = ClassificationOverride(
            original_class=current_result.predicted_class,
            overridden_class=overridden_class,
            overridden_by=overridden_by,
            reason=reason,
        )

        current_result.manual_override = override
        current_result.effective_class = overridden_class

        # Re-persist artifact
        art_data = current_result.model_dump_json(indent=2).encode("utf-8")
        art_name = f"classification_{current_result.processing_run_id}.json"
        key, sha256 = self.storage.store_artifact(
            case_id=case_id,
            document_id=document_id,
            processing_run_id=current_result.processing_run_id,
            artifact_filename=art_name,
            data=art_data,
        )
        current_result.storage_artifact_key = key
        current_result.storage_artifact_sha256 = sha256

        # Update document entity
        try:
            doc.document_type = DocumentType(overridden_class.value)
            self.document_repo.save(doc)
        except (ValueError, KeyError):
            pass

        # Record audit event (overridden_by is an asserted reviewer identifier in development mode)
        self.audit_service.record_event(
            case_id=case_id,
            event_type=AuditEventType.DOCUMENT_CLASSIFICATION_OVERRIDDEN,
            entity_type=EntityType.DOCUMENT,
            entity_id=document_id,
            actor_id=overridden_by,
            payload={
                "original_class": override.original_class.value,
                "overridden_class": override.overridden_class.value,
                "reason": reason,
                "overridden_by": overridden_by,
                "asserted_reviewer_id": overridden_by,
                "processing_run_id": current_result.processing_run_id,
            },
        )

        return current_result

    def extract_fields(
        self,
        case_id: str,
        document_id: str,
        schema_id: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> DocumentExtractionResult:
        """Extract structured fields against an explicit schema and persist field evidence nodes."""
        case, doc = self._get_validated_doc_and_case(case_id, document_id)
        self._ensure_case_not_archived(case)

        extracted_doc = self._get_or_run_ocr(case_id, document_id)

        # Resolve extraction schema
        schema: ExtractionSchema | None = None
        if schema_id:
            schema = self.schema_registry.get_by_id(schema_id)
            if not schema:
                raise NotFoundException(f"Extraction schema '{schema_id}' not found.")
        else:
            # Auto-resolve schema via classification
            try:
                class_res = self.get_latest_classification(case_id, document_id)
            except NotFoundException:
                class_res = self.classify_document(case_id, document_id)

            schema = self.schema_registry.get_default_for_class(class_res.effective_class)
            if not schema:
                raise ValidationException(
                    f"No extraction schema registered for document class '{class_res.effective_class}'. "
                    f"Supported schemas: {[s.schema_id for s in self.schema_registry.list_schemas()]}"
                )

        # Create processing run
        run = ProcessingRun(
            case_id=case_id,
            document_ids=[document_id],
            pipeline_name=f"structured-extraction-{schema.schema_id}",
            pipeline_version=schema.version,
            status=PipelineStatus.RUNNING,
        )
        self.run_repo.save(run)

        try:
            result = self.extractor.extract_fields(extracted_doc, schema, options=options)
            result.processing_run_id = run.id

            # Create traceable EvidenceNode for each extracted field
            for field_key, field_val in result.fields.items():
                box = (
                    field_val.source_bounding_boxes[0] if field_val.source_bounding_boxes else None
                )

                # Ensure sensitive fields (e.g. account numbers) never store unmasked plaintext in EvidenceNode
                raw_val_str = (
                    str(field_val.normalized_value)
                    if field_val.data_type == FieldDataType.MASKED_STRING
                    else field_val.raw_text
                )

                ev_node = EvidenceNode(
                    case_id=case_id,
                    document_id=document_id,
                    processing_run_id=run.id,
                    evidence_type=EvidenceType.EXTRACTED_FIELD,
                    title=f"Field: {field_val.label} ({field_key})",
                    description=f"Extracted {field_val.label} from page {field_val.source_page_number} via {field_val.extraction_method}.",
                    source_component="structured-field-extractor",
                    source_version=schema.version,
                    page_number=field_val.source_page_number,
                    bounding_box=box,
                    coordinate_system=CoordinateSystem.NORMALIZED_0_1 if box else None,
                    raw_value=raw_val_str,
                    normalized_value=str(field_val.normalized_value)
                    if field_val.normalized_value is not None
                    else None,
                    categorical_confidence="high"
                    if field_val.validation_status == FieldValidationStatus.VALID
                    else "medium",
                    confidence_source=field_val.extraction_method,
                    confidence=None,  # Nullable for deterministic extraction
                    metadata={
                        "field_key": field_key,
                        "data_type": field_val.data_type.value,
                        "schema_id": schema.schema_id,
                        "schema_version": schema.version,
                        "validation_status": field_val.validation_status.value,
                        "warnings": field_val.warnings,
                        "source_token_ids": field_val.source_token_ids,
                        "score": field_val.score,
                    },
                )
                self.evidence_repo.save(ev_node)
                field_val.evidence_node_id = ev_node.id

            # Persist full extraction JSON artifact
            art_data = result.model_dump_json(indent=2).encode("utf-8")
            art_name = f"extraction_{run.id}.json"
            key, sha256 = self.storage.store_artifact(
                case_id=case_id,
                document_id=document_id,
                processing_run_id=run.id,
                artifact_filename=art_name,
                data=art_data,
            )
            result.storage_artifact_key = key
            result.storage_artifact_sha256 = sha256

            # Mark run succeeded
            run.mark_succeeded()
            self.run_repo.save(run)

            # Record audit event
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.FIELDS_EXTRACTED,
                entity_type=EntityType.DOCUMENT,
                entity_id=document_id,
                actor_id="system",
                payload={
                    "schema_id": schema.schema_id,
                    "schema_version": schema.version,
                    "fields_extracted_count": len(result.fields),
                    "processing_run_id": run.id,
                },
            )

            return result

        except Exception as exc:
            logger.exception("Structured field extraction failed")
            run.mark_failed(error_code="EXTRACTION_FAILED", error_message=str(exc))
            self.run_repo.save(run)
            raise

    def get_latest_extraction(
        self, case_id: str, document_id: str, expected_sha256: str | None = None
    ) -> DocumentExtractionResult:
        """Retrieve latest structured extraction result for a document."""
        self._get_validated_doc_and_case(case_id, document_id)

        runs, _ = self.run_repo.list_by_case(case_id=case_id, document_id=document_id)
        ext_runs = [
            r
            for r in runs
            if r.status == PipelineStatus.SUCCEEDED
            and "structured-extraction" in r.pipeline_name.lower()
        ]
        if not ext_runs:
            raise NotFoundException(
                f"No structured field extraction results found for document '{document_id}'."
            )

        latest_run = sorted(ext_runs, key=lambda r: r.started_at, reverse=True)[0]
        filename = f"extraction_{latest_run.id}.json"
        raw_bytes = self._read_artifact(
            case_id=case_id,
            document_id=document_id,
            processing_run_id=latest_run.id,
            artifact_filename=filename,
            expected_sha256=expected_sha256,
        )
        return DocumentExtractionResult.model_validate_json(raw_bytes.decode("utf-8"))
