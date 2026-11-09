"""Repository interface and SQLAlchemy implementation for EvidenceNode records."""

from datetime import UTC

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import CoordinateSystem, EvidenceType
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.infrastructure.persistence.models import EvidenceNodeModel


class EvidenceRepository:
    """Repository handling persistence and retrieval of EvidenceNode records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, evidence: EvidenceNode) -> EvidenceNode:
        """Persist or update EvidenceNode entity."""
        existing = self.db.get(EvidenceNodeModel, evidence.id)
        if existing:
            existing.title = evidence.title
            existing.description = evidence.description
            existing.categorical_confidence = evidence.categorical_confidence
            existing.confidence_source = evidence.confidence_source
            existing.confidence = evidence.confidence
            existing.node_metadata = evidence.metadata
        else:
            bbox_dict = (
                evidence.bounding_box.to_normalized_dict() if evidence.bounding_box else None
            )
            coord_sys = evidence.coordinate_system.value if evidence.coordinate_system else None
            model = EvidenceNodeModel(
                id=evidence.id,
                case_id=evidence.case_id,
                document_id=evidence.document_id,
                processing_run_id=evidence.processing_run_id,
                evidence_type=evidence.evidence_type.value,
                title=evidence.title,
                description=evidence.description,
                source_component=evidence.source_component,
                source_version=evidence.source_version,
                observed_at=evidence.observed_at,
                page_number=evidence.page_number,
                bounding_box=bbox_dict,
                coordinate_system=coord_sys,
                pdf_object_reference=evidence.pdf_object_reference,
                byte_offset_start=evidence.byte_offset_start,
                byte_offset_end=evidence.byte_offset_end,
                raw_value=evidence.raw_value,
                normalized_value=evidence.normalized_value,
                categorical_confidence=evidence.categorical_confidence,
                confidence_source=evidence.confidence_source,
                confidence=evidence.confidence,
                node_metadata=evidence.metadata,
            )
            self.db.add(model)
        self.db.commit()
        return evidence

    def save_bulk(self, evidence_list: list[EvidenceNode]) -> None:
        """Bulk persist EvidenceNode entities within the current transaction."""
        for ev in evidence_list:
            bbox_dict = ev.bounding_box.to_normalized_dict() if ev.bounding_box else None
            coord_sys = ev.coordinate_system.value if ev.coordinate_system else None
            model = EvidenceNodeModel(
                id=ev.id,
                case_id=ev.case_id,
                document_id=ev.document_id,
                processing_run_id=ev.processing_run_id,
                evidence_type=ev.evidence_type.value,
                title=ev.title,
                description=ev.description,
                source_component=ev.source_component,
                source_version=ev.source_version,
                observed_at=ev.observed_at,
                page_number=ev.page_number,
                bounding_box=bbox_dict,
                coordinate_system=coord_sys,
                pdf_object_reference=ev.pdf_object_reference,
                byte_offset_start=ev.byte_offset_start,
                byte_offset_end=ev.byte_offset_end,
                raw_value=ev.raw_value,
                normalized_value=ev.normalized_value,
                categorical_confidence=ev.categorical_confidence,
                confidence_source=ev.confidence_source,
                confidence=ev.confidence,
                node_metadata=ev.metadata,
            )
            self.db.add(model)
        self.db.commit()

    def get_by_id(self, evidence_id: str) -> EvidenceNode | None:
        """Retrieve EvidenceNode by ID."""
        model = self.db.get(EvidenceNodeModel, evidence_id)
        if not model:
            return None
        return self._to_domain(model)

    def list_by_case(
        self,
        case_id: str,
        document_id: str | None = None,
        processing_run_id: str | None = None,
        evidence_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[EvidenceNode], int]:
        """List evidence nodes for a case with optional filters and pagination."""
        stmt = select(EvidenceNodeModel).where(EvidenceNodeModel.case_id == case_id)
        if document_id:
            stmt = stmt.where(EvidenceNodeModel.document_id == document_id)
        if processing_run_id:
            stmt = stmt.where(EvidenceNodeModel.processing_run_id == processing_run_id)
        if evidence_type:
            stmt = stmt.where(EvidenceNodeModel.evidence_type == evidence_type)

        total = len(list(self.db.scalars(stmt).all()))
        paginated_stmt = (
            stmt.order_by(desc(EvidenceNodeModel.observed_at)).offset(skip).limit(limit)
        )
        models = self.db.scalars(paginated_stmt).all()

        return [self._to_domain(m) for m in models], total

    @staticmethod
    def _to_domain(m: EvidenceNodeModel) -> EvidenceNode:
        observed = m.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)

        bbox = None
        if m.bounding_box and isinstance(m.bounding_box, dict):
            bbox = BoundingBox(
                x=m.bounding_box.get("x", 0.0),
                y=m.bounding_box.get("y", 0.0),
                width=m.bounding_box.get("width", 0.0),
                height=m.bounding_box.get("height", 0.0),
            )

        coord_sys = CoordinateSystem(m.coordinate_system) if m.coordinate_system else None

        return EvidenceNode(
            id=m.id,
            case_id=m.case_id,
            document_id=m.document_id,
            processing_run_id=m.processing_run_id,
            evidence_type=EvidenceType(m.evidence_type),
            title=m.title,
            description=m.description,
            source_component=m.source_component,
            source_version=m.source_version,
            observed_at=observed,
            page_number=m.page_number,
            bounding_box=bbox,
            coordinate_system=coord_sys,
            pdf_object_reference=m.pdf_object_reference,
            byte_offset_start=m.byte_offset_start,
            byte_offset_end=m.byte_offset_end,
            raw_value=m.raw_value,
            normalized_value=m.normalized_value,
            categorical_confidence=m.categorical_confidence,
            confidence_source=m.confidence_source,
            confidence=m.confidence,
            metadata=dict(m.node_metadata or {}),
        )
