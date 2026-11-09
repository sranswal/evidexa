"""Repository interface and SQLAlchemy implementation for ProcessingRun entities."""

from datetime import UTC

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.infrastructure.persistence.models import ProcessingRunModel


class ProcessingRunRepository:
    """Repository handling persistence and retrieval of ProcessingRun records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, run: ProcessingRun) -> ProcessingRun:
        """Persist or update ProcessingRun entity."""
        existing = self.db.get(ProcessingRunModel, run.id)
        if existing:
            existing.status = run.status.value
            existing.completed_at = run.completed_at
            existing.snapshot_sha256 = run.snapshot_sha256
            existing.error_code = run.error_code
            existing.error_message = run.error_message
            existing.configuration_snapshot = run.configuration_snapshot
            existing.resource_metrics = run.resource_metrics
        else:
            model = ProcessingRunModel(
                id=run.id,
                case_id=run.case_id,
                document_ids=run.document_ids,
                pipeline_name=run.pipeline_name,
                pipeline_version=run.pipeline_version,
                status=run.status.value,
                started_at=run.started_at,
                completed_at=run.completed_at,
                snapshot_sha256=run.snapshot_sha256,
                error_code=run.error_code,
                error_message=run.error_message,
                configuration_snapshot=run.configuration_snapshot,
                resource_metrics=run.resource_metrics,
            )
            self.db.add(model)
        self.db.commit()
        return run

    def get_by_id(self, run_id: str) -> ProcessingRun | None:
        """Retrieve ProcessingRun by ID."""
        model = self.db.get(ProcessingRunModel, run_id)
        if not model:
            return None
        return self._to_domain(model)

    def list_by_case(
        self,
        case_id: str,
        document_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ProcessingRun], int]:
        """List processing runs for a case with optional document filter and pagination."""
        stmt = select(ProcessingRunModel).where(ProcessingRunModel.case_id == case_id)
        if document_id:
            # document_ids is stored as JSON array; filter matching document_id in list
            stmt = stmt.where(ProcessingRunModel.document_ids.contains(document_id))

        total = len(list(self.db.scalars(stmt).all()))
        paginated_stmt = (
            stmt.order_by(desc(ProcessingRunModel.started_at)).offset(skip).limit(limit)
        )
        models = self.db.scalars(paginated_stmt).all()

        return [self._to_domain(m) for m in models], total

    def list_by_status(self, status: PipelineStatus) -> list[ProcessingRun]:
        """Retrieve all processing runs with the specified status."""
        stmt = select(ProcessingRunModel).where(ProcessingRunModel.status == status.value)
        models = self.db.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(m: ProcessingRunModel) -> ProcessingRun:
        started = m.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)

        completed = m.completed_at
        if completed and completed.tzinfo is None:
            completed = completed.replace(tzinfo=UTC)

        return ProcessingRun(
            id=m.id,
            case_id=m.case_id,
            document_ids=list(m.document_ids or []),
            pipeline_name=m.pipeline_name,
            pipeline_version=m.pipeline_version,
            status=PipelineStatus(m.status),
            started_at=started,
            completed_at=completed,
            snapshot_sha256=m.snapshot_sha256,
            error_code=m.error_code,
            error_message=m.error_message,
            configuration_snapshot=dict(m.configuration_snapshot or {}),
            resource_metrics=dict(m.resource_metrics or {}) if m.resource_metrics else None,
        )
