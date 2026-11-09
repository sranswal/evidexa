"""Repository interface and SQLAlchemy implementation for Case aggregates."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import CaseStatus
from document_intelligence.domain.models.case import Case
from document_intelligence.infrastructure.persistence.models import CaseModel


class CaseRepository:
    """Repository handling persistence and retrieval of Case aggregates."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, case: Case) -> Case:
        """Persist or update a Case aggregate."""
        existing = self.db.get(CaseModel, case.id)
        if existing:
            existing.case_reference = case.case_reference
            existing.title = case.title
            existing.description = case.description
            existing.status = case.status.value
            existing.updated_at = case.updated_at
            existing.created_by = case.created_by
            existing.case_metadata = case.metadata
        else:
            model = CaseModel(
                id=case.id,
                case_reference=case.case_reference,
                title=case.title,
                description=case.description,
                status=case.status.value,
                created_at=case.created_at,
                updated_at=case.updated_at,
                created_by=case.created_by,
                case_metadata=case.metadata,
            )
            self.db.add(model)
        self.db.commit()
        return case

    def get_by_id(self, case_id: str) -> Case | None:
        """Retrieve Case by UUID primary key."""
        model = self.db.get(CaseModel, case_id)
        if not model:
            return None
        return self._to_domain(model)

    def get_by_reference(self, reference: str) -> Case | None:
        """Retrieve Case by human-readable reference."""
        stmt = select(CaseModel).where(CaseModel.case_reference == reference)
        model = self.db.scalar(stmt)
        if not model:
            return None
        return self._to_domain(model)

    def list_cases(
        self,
        skip: int = 0,
        limit: int = 50,
        status: CaseStatus | None = None,
    ) -> tuple[list[Case], int]:
        """List cases with pagination and optional status filter."""
        stmt = select(CaseModel)
        if status:
            stmt = stmt.where(CaseModel.status == status.value)

        total_stmt = select(CaseModel)
        if status:
            total_stmt = total_stmt.where(CaseModel.status == status.value)

        # Count total matches
        total = len(list(self.db.scalars(total_stmt).all()))

        # Paginate
        paginated_stmt = stmt.order_by(CaseModel.created_at.desc()).offset(skip).limit(limit)
        models = self.db.scalars(paginated_stmt).all()

        return [self._to_domain(m) for m in models], total

    @staticmethod
    def _to_domain(m: CaseModel) -> Case:
        return Case(
            id=m.id,
            case_reference=m.case_reference,
            title=m.title,
            description=m.description,
            status=CaseStatus(m.status),
            created_at=m.created_at,
            updated_at=m.updated_at,
            created_by=m.created_by,
            metadata=dict(m.case_metadata or {}),
        )
