"""Repository interface and SQLAlchemy implementation for AuditEvent records."""

from datetime import UTC

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import AuditEventType, EntityType
from document_intelligence.domain.models.audit_event import AuditCheckpoint, AuditEvent
from document_intelligence.infrastructure.persistence.models import (
    AuditCheckpointModel,
    AuditEventModel,
)


class AuditRepository:
    """Repository handling append-only persistence and chain traversal of AuditEvent records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, event: AuditEvent) -> AuditEvent:
        """Append an immutable audit event to the ledger and update the head checkpoint."""
        model = AuditEventModel(
            id=event.id,
            case_id=event.case_id,
            sequence_number=event.sequence_number,
            actor_id=event.actor_id,
            event_type=event.event_type.value,
            entity_type=event.entity_type.value,
            entity_id=event.entity_id,
            timestamp=event.timestamp,
            payload=event.payload,
            previous_event_hash=event.previous_event_hash,
            event_hash=event.event_hash,
            schema_version=event.schema_version,
        )
        self.db.add(model)

        # Update or create checkpoint transactionally
        checkpoint_model = self.db.get(AuditCheckpointModel, event.case_id)
        if checkpoint_model is None:
            checkpoint_model = AuditCheckpointModel(
                case_id=event.case_id,
                head_event_id=event.id,
                head_event_hash=event.event_hash,
                event_count=1,
                updated_at=event.timestamp,
            )
            self.db.add(checkpoint_model)
        else:
            checkpoint_model.head_event_id = event.id
            checkpoint_model.head_event_hash = event.event_hash
            checkpoint_model.event_count += 1
            checkpoint_model.updated_at = event.timestamp

        self.db.commit()
        return event

    def get_latest_event(self, case_id: str) -> AuditEvent | None:
        """Fetch the latest event for a case to retrieve the latest hash and sequence number."""
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.case_id == case_id)
            .order_by(desc(AuditEventModel.sequence_number), desc(AuditEventModel.id))
            .limit(1)
        )
        model = self.db.scalar(stmt)
        if not model:
            return None
        return self._to_domain(model)

    def get_checkpoint(self, case_id: str) -> AuditCheckpoint | None:
        """Fetch the trusted head checkpoint for a case."""
        model = self.db.get(AuditCheckpointModel, case_id)
        if not model:
            return None
        ts = model.updated_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return AuditCheckpoint(
            case_id=model.case_id,
            head_event_id=model.head_event_id,
            head_event_hash=model.head_event_hash,
            event_count=model.event_count,
            updated_at=ts,
        )

    def list_by_case(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AuditEvent], int]:
        """Retrieve audit events for a case in chronological order with pagination."""
        stmt = select(AuditEventModel).where(AuditEventModel.case_id == case_id)
        total = len(list(self.db.scalars(stmt).all()))

        paginated_stmt = (
            stmt.order_by(AuditEventModel.sequence_number.asc()).offset(skip).limit(limit)
        )
        models = self.db.scalars(paginated_stmt).all()

        return [self._to_domain(m) for m in models], total

    def get_all_for_chain_verification(self, case_id: str) -> list[AuditEvent]:
        """Fetch entire chronological sequence of events for a case to verify hash chain integrity."""
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.case_id == case_id)
            .order_by(AuditEventModel.sequence_number.asc(), AuditEventModel.id.asc())
        )
        models = self.db.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(m: AuditEventModel) -> AuditEvent:
        ts = m.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return AuditEvent(
            id=m.id,
            case_id=m.case_id,
            sequence_number=m.sequence_number,
            actor_id=m.actor_id,
            event_type=AuditEventType(m.event_type),
            entity_type=EntityType(m.entity_type),
            entity_id=m.entity_id,
            timestamp=ts,
            payload=dict(m.payload or {}),
            previous_event_hash=m.previous_event_hash,
            event_hash=m.event_hash,
            schema_version=m.schema_version,
        )
