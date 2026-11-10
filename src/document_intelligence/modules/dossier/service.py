"""Investigation dossier application service.

Coordinates findings aggregation, investigator reviews, deterministic dossier compilation,
integrity finalization, and export rendering with cryptographic audit logging.
"""

from __future__ import annotations

from document_intelligence.core.exceptions import (
    NotFoundException,
    SecurityException,
    ValidationException,
)
from document_intelligence.domain.enums import (
    AuditEventType,
    CaseStatus,
    DossierFormat,
    DossierStatus,
    EntityType,
    EvidentiaryClassification,
    InvestigatorReviewAction,
)
from document_intelligence.domain.models.aggregated_finding import (
    AggregatedFinding,
    AggregatedFindingReview,
)
from document_intelligence.domain.models.investigation_dossier import InvestigationDossier
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.consistency_repository import (
    ConsistencyRepository,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.dossier_repository import (
    DossierRepository,
)
from document_intelligence.infrastructure.repositories.entity_match_repository import (
    EntityMatchRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.finding_repository import (
    FindingRepository,
)
from document_intelligence.infrastructure.repositories.relationship_repository import (
    RelationshipRepository,
)
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.dossier.aggregator import FindingsAggregator
from document_intelligence.modules.dossier.export.json_exporter import JsonDossierExporter
from document_intelligence.modules.dossier.export.pdf_exporter import PdfDossierExporter
from document_intelligence.modules.dossier.generator import (
    DossierGenerator,
    compute_canonical_content_hash,
)


class InvestigationDossierService:
    """Application service for aggregated findings and evidence dossiers."""

    def __init__(
        self,
        case_repo: CaseRepository,
        document_repo: DocumentRepository,
        finding_repo: FindingRepository,
        consistency_repo: ConsistencyRepository,
        relationship_repo: RelationshipRepository,
        entity_match_repo: EntityMatchRepository,
        evidence_repo: EvidenceRepository,
        dossier_repo: DossierRepository,
        audit_service: AuditLedgerService | None = None,
        aggregator: FindingsAggregator | None = None,
        generator: DossierGenerator | None = None,
        pdf_exporter: PdfDossierExporter | None = None,
        json_exporter: JsonDossierExporter | None = None,
    ) -> None:
        self.case_repo = case_repo
        self.document_repo = document_repo
        self.finding_repo = finding_repo
        self.consistency_repo = consistency_repo
        self.relationship_repo = relationship_repo
        self.entity_match_repo = entity_match_repo
        self.evidence_repo = evidence_repo
        self.dossier_repo = dossier_repo
        self.audit_service = audit_service
        self.aggregator = aggregator or FindingsAggregator()
        self.generator = generator or DossierGenerator()
        self.pdf_exporter = pdf_exporter or PdfDossierExporter()
        self.json_exporter = json_exporter or JsonDossierExporter()

    def get_aggregated_findings(self, case_id: str) -> list[AggregatedFinding]:
        """Aggregate findings across all forensic and intelligence subsystems for a case."""
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundException(f"Case '{case_id}' not found")

        forensic_findings, _ = self.finding_repo.list_by_case(case_id)
        consistency_findings = self.consistency_repo.list_findings(case_id, limit=1000)
        relationships, _ = self.relationship_repo.list_relationships(case_id, limit=1000)
        entity_matches, _ = self.entity_match_repo.list_matches(case_id, limit=1000)
        reviews = self.dossier_repo.list_aggregated_reviews(case_id)

        return self.aggregator.aggregate(
            case_id=case_id,
            forensic_findings=forensic_findings,
            consistency_findings=consistency_findings,
            detected_relationships=relationships,
            entity_matches=entity_matches,
            reviews=reviews,
        )

    def record_finding_review(
        self,
        case_id: str,
        finding_id: str,
        reviewer_id: str,
        action: InvestigatorReviewAction,
        rationale: str,
    ) -> AggregatedFindingReview:
        """Record an append-only investigator review assertion on an aggregated finding."""
        if not reviewer_id or not reviewer_id.strip():
            raise ValidationException("Reviewer ID cannot be empty.")
        if not rationale or not rationale.strip():
            raise ValidationException("Review rationale cannot be empty.")

        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundException(f"Case '{case_id}' not found")
        if case.status == CaseStatus.ARCHIVED:
            raise SecurityException(f"Cannot record review decisions on archived case '{case.id}'.")

        findings = self.get_aggregated_findings(case_id)
        target = next((f for f in findings if f.id == finding_id), None)
        if not target:
            raise NotFoundException(
                f"Aggregated finding '{finding_id}' not found in case '{case_id}'"
            )

        review = AggregatedFindingReview(
            finding_id=finding_id,
            case_id=case_id,
            reviewer_id=reviewer_id,
            action=action,
            prior_status=target.review_status,
            new_status=action.value,
            rationale=rationale.strip(),
            evidentiary_classification=EvidentiaryClassification.INVESTIGATOR_CONCLUSION,
        )

        persisted = self.dossier_repo.add_aggregated_review(review)

        if self.audit_service:
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.REVIEW_DECISION_RECORDED,
                entity_type=EntityType.AGGREGATED_FINDING,
                entity_id=finding_id,
                payload={
                    "review_id": persisted.id,
                    "action": action.value,
                    "prior_status": target.review_status,
                    "new_status": action.value,
                    "reviewer_id": reviewer_id,
                    "rationale": rationale,
                },
                actor_id=reviewer_id,
            )

        return persisted

    def list_finding_reviews(self, case_id: str, finding_id: str) -> list[AggregatedFindingReview]:
        """List chronological review history for a specific aggregated finding."""
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundException(f"Case '{case_id}' not found")
        return self.dossier_repo.list_reviews_for_finding(case_id, finding_id)

    def generate_dossier(
        self,
        case_id: str,
        created_by: str,
        scope_and_purpose: str | None = None,
    ) -> InvestigationDossier:
        """Compile and persist an investigation dossier draft."""
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundException(f"Case '{case_id}' not found")
        if case.status == CaseStatus.ARCHIVED:
            raise SecurityException(f"Cannot generate dossiers for archived case '{case.id}'.")

        documents, _ = self.document_repo.list_by_case(case_id)
        aggregated_findings = self.get_aggregated_findings(case_id)
        reviews = self.dossier_repo.list_aggregated_reviews(case_id)
        evidence_nodes, _ = self.evidence_repo.list_by_case(case_id, limit=1000)
        relationships, _ = self.relationship_repo.list_relationships(case_id, limit=1000)

        existing_dossiers = self.dossier_repo.list_by_case(case_id)
        version = max((d.version for d in existing_dossiers), default=0) + 1

        dossier = self.generator.generate(
            case=case,
            documents=documents,
            aggregated_findings=aggregated_findings,
            reviews=reviews,
            evidence_nodes=evidence_nodes,
            relationships=relationships,
            scope_and_purpose=scope_and_purpose,
            created_by=created_by,
            version=version,
        )

        saved = self.dossier_repo.save_dossier(dossier)

        if self.audit_service:
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.DOSSIER_CREATED,
                entity_type=EntityType.DOSSIER,
                entity_id=saved.id,
                payload={
                    "dossier_id": saved.id,
                    "version": saved.version,
                    "title": saved.title,
                    "document_count": len(documents),
                    "finding_count": len(aggregated_findings),
                },
                actor_id=created_by,
            )

        return saved

    def get_dossier(self, case_id: str, dossier_id: str) -> InvestigationDossier:
        """Retrieve dossier by ID with case verification."""
        dossier = self.dossier_repo.get_by_id(dossier_id)
        if not dossier or dossier.case_id != case_id:
            raise NotFoundException(f"Dossier '{dossier_id}' not found in case '{case_id}'")
        return dossier

    def list_dossiers(self, case_id: str) -> list[InvestigationDossier]:
        """List all dossiers for a case."""
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundException(f"Case '{case_id}' not found")
        return self.dossier_repo.list_by_case(case_id)

    def finalize_dossier(self, case_id: str, dossier_id: str, user_id: str) -> InvestigationDossier:
        """Freeze and seal dossier with cryptographic content hash."""
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundException(f"Case '{case_id}' not found")
        if case.status == CaseStatus.ARCHIVED:
            raise SecurityException(f"Cannot finalize dossiers for archived case '{case.id}'.")

        dossier = self.get_dossier(case_id, dossier_id)
        if dossier.status == DossierStatus.APPROVED:
            return dossier

        content_hash = compute_canonical_content_hash(dossier.dossier_payload)
        dossier.finalize(content_hash=content_hash, snapshot_payload=dossier.dossier_payload)

        updated = self.dossier_repo.save_dossier(dossier)

        if self.audit_service:
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.DOSSIER_FINALIZED,
                entity_type=EntityType.DOSSIER,
                entity_id=updated.id,
                payload={
                    "dossier_id": updated.id,
                    "version": updated.version,
                    "content_hash": content_hash,
                },
                actor_id=user_id,
            )

        return updated

    def export_dossier(
        self,
        case_id: str,
        dossier_id: str,
        export_format: DossierFormat,
        user_id: str,
    ) -> tuple[bytes, str, str]:
        """Render and export dossier in PDF or JSON format.

        Returns (content_bytes, media_type, filename).
        """
        dossier = self.get_dossier(case_id, dossier_id)

        short_case = dossier.case_id[:8]
        if export_format == DossierFormat.PDF:
            content = self.pdf_exporter.export(dossier)
            media_type = "application/pdf"
            file_name = f"evidexa_dossier_{short_case}_v{dossier.version}.pdf"
        elif export_format == DossierFormat.JSON:
            content = self.json_exporter.export(dossier).encode("utf-8")
            media_type = "application/json"
            file_name = f"evidexa_dossier_{short_case}_v{dossier.version}.json"
        else:
            raise ValidationException(f"Unsupported dossier export format: {export_format}")

        if self.audit_service:
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.EXPORT_GENERATED,
                entity_type=EntityType.DOSSIER,
                entity_id=dossier.id,
                payload={
                    "format": export_format.value,
                    "file_name": file_name,
                    "byte_count": len(content),
                },
                actor_id=user_id,
            )

        return content, media_type, file_name
