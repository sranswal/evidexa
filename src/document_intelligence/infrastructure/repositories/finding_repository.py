"""Repository interface and SQLAlchemy implementation for ForensicFinding entities."""

from datetime import UTC

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.infrastructure.persistence.models import (
    FindingEvidenceLinkModel,
    ForensicFindingModel,
)


class FindingRepository:
    """Repository handling persistence and retrieval of ForensicFinding entities."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, finding: ForensicFinding) -> ForensicFinding:
        """Persist or update ForensicFinding entity."""
        existing = self.db.get(ForensicFindingModel, finding.id)
        if existing:
            existing.status = finding.status.value
            existing.severity = finding.severity.value
            existing.categorical_confidence = finding.categorical_confidence
            existing.confidence_source = finding.confidence_source
            existing.confidence_calibration_method = finding.confidence_calibration_method
            existing.confidence = finding.confidence
            existing.evidence_ids = finding.evidence_ids
            existing.limitations = finding.limitations
            existing.finding_metadata = finding.metadata
        else:
            model = ForensicFindingModel(
                id=finding.id,
                case_id=finding.case_id,
                document_id=finding.document_id,
                processing_run_id=finding.processing_run_id,
                category=finding.category.value,
                title=finding.title,
                description=finding.description,
                severity=finding.severity.value,
                categorical_confidence=finding.categorical_confidence,
                confidence_source=finding.confidence_source,
                confidence_calibration_method=finding.confidence_calibration_method,
                confidence=finding.confidence,
                status=finding.status.value,
                evidence_ids=finding.evidence_ids,
                created_at=finding.created_at,
                source_component=finding.source_component,
                limitations=finding.limitations,
                finding_metadata=finding.metadata,
            )
            self.db.add(model)
        self.db.commit()
        return finding

    def save_bulk(
        self,
        findings: list[ForensicFinding],
        links: list[tuple[str, str]] | None = None,
    ) -> None:
        """Bulk persist findings and their evidence association links."""
        for f in findings:
            model = ForensicFindingModel(
                id=f.id,
                case_id=f.case_id,
                document_id=f.document_id,
                processing_run_id=f.processing_run_id,
                category=f.category.value,
                title=f.title,
                description=f.description,
                severity=f.severity.value,
                categorical_confidence=f.categorical_confidence,
                confidence_source=f.confidence_source,
                confidence_calibration_method=f.confidence_calibration_method,
                confidence=f.confidence,
                status=f.status.value,
                evidence_ids=f.evidence_ids,
                created_at=f.created_at,
                source_component=f.source_component,
                limitations=f.limitations,
                finding_metadata=f.metadata,
            )
            self.db.add(model)

        # Flush findings first so foreign keys exist before inserting link rows
        self.db.flush()

        if links:
            for finding_id, evidence_id in links:
                link_model = FindingEvidenceLinkModel(
                    finding_id=finding_id, evidence_id=evidence_id
                )
                self.db.add(link_model)

        self.db.commit()

    def get_by_id(self, finding_id: str) -> ForensicFinding | None:
        """Retrieve finding by ID."""
        model = self.db.get(ForensicFindingModel, finding_id)
        if not model:
            return None
        return self._to_domain(model)

    def list_by_case(
        self,
        case_id: str,
        document_id: str | None = None,
        processing_run_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ForensicFinding], int]:
        """List findings for a case with optional filters and pagination."""
        stmt = select(ForensicFindingModel).where(ForensicFindingModel.case_id == case_id)
        if document_id:
            stmt = stmt.where(ForensicFindingModel.document_id == document_id)
        if processing_run_id:
            stmt = stmt.where(ForensicFindingModel.processing_run_id == processing_run_id)

        total = len(list(self.db.scalars(stmt).all()))

        paginated_stmt = (
            stmt.order_by(desc(ForensicFindingModel.created_at)).offset(skip).limit(limit)
        )
        models = self.db.scalars(paginated_stmt).all()

        return [self._to_domain(m) for m in models], total

    @staticmethod
    def _to_domain(m: ForensicFindingModel) -> ForensicFinding:
        created = m.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)

        return ForensicFinding(
            id=m.id,
            case_id=m.case_id,
            document_id=m.document_id,
            processing_run_id=m.processing_run_id,
            category=FindingCategory(m.category),
            title=m.title,
            description=m.description,
            severity=FindingSeverity(m.severity),
            categorical_confidence=m.categorical_confidence,
            confidence_source=m.confidence_source,
            confidence_calibration_method=m.confidence_calibration_method,
            confidence=m.confidence,
            status=FindingStatus(m.status),
            evidence_ids=list(m.evidence_ids or []),
            created_at=created,
            source_component=m.source_component,
            limitations=list(m.limitations or []),
            metadata=dict(m.finding_metadata or {}),
        )
