"""SQLAlchemy repository for detected relationships and human review audit trail."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    DuplicateKind,
    RelationshipDetectionMethod,
    RelationshipReviewAction,
    RelationshipStatus,
    RelationshipType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipEvidence,
    RelationshipReviewRecord,
)
from document_intelligence.infrastructure.persistence.models import (
    DetectedRelationshipModel,
    RelationshipReviewModel,
)


class RelationshipRepository:
    """Provides relational persistence for detected relationships and review history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_relationship(self, rel: DetectedRelationship) -> None:
        """Upsert a detected relationship."""
        model = self.session.get(DetectedRelationshipModel, rel.id)
        status_det = (
            rel.status_determination_method.value
            if hasattr(rel.status_determination_method, "value")
            else str(rel.status_determination_method)
        )
        dup_kind = rel.duplicate_kind.value if rel.duplicate_kind is not None else None

        if model is None:
            model = DetectedRelationshipModel(
                id=rel.id,
                case_id=rel.case_id,
                detection_run_id=rel.detection_run_id,
                relationship_type=rel.relationship_type.value,
                ontology_version=rel.ontology_version,
                legacy_relationship_type=rel.legacy_relationship_type,
                source_id=rel.source_id,
                source_type=rel.source_type,
                source_label=rel.source_label,
                target_id=rel.target_id,
                target_type=rel.target_type,
                target_label=rel.target_label,
                direction_display=rel.direction_display,
                status=rel.status.value,
                status_determination_method=status_det,
                duplicate_kind=dup_kind,
                score=rel.score,
                score_semantics=rel.score_semantics,
                detection_method=rel.detection_method.value,
                detection_version=rel.detection_version,
                status_rationale=rel.status_rationale,
                evidence_payload=rel.evidence.model_dump(),
                created_at=rel.created_at,
                updated_at=rel.updated_at,
            )
            self.session.add(model)
        else:
            model.status = rel.status.value
            model.status_determination_method = status_det
            model.duplicate_kind = dup_kind
            model.score = rel.score
            model.status_rationale = rel.status_rationale
            model.evidence_payload = rel.evidence.model_dump()
            model.updated_at = rel.updated_at

        self.session.flush()

    def save_relationships(self, rels: list[DetectedRelationship]) -> None:
        """Batch save detected relationships."""
        for r in rels:
            self.save_relationship(r)
        self.session.flush()

    def get_relationship_by_id(
        self, case_id: str, relationship_id: str
    ) -> DetectedRelationship | None:
        """Retrieve relationship by ID, ensuring case isolation."""
        stmt = select(DetectedRelationshipModel).where(
            DetectedRelationshipModel.case_id == case_id,
            DetectedRelationshipModel.id == relationship_id,
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        if model is None:
            return None

        reviews = self.list_reviews_for_relationship(case_id, relationship_id)
        return self._to_domain(model, reviews)

    def list_relationships(
        self,
        case_id: str,
        relationship_type: str | None = None,
        status: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        detection_run_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[DetectedRelationship], int]:
        """List and paginate detected relationships with filtering."""
        stmt = select(DetectedRelationshipModel).where(DetectedRelationshipModel.case_id == case_id)

        if relationship_type:
            stmt = stmt.where(DetectedRelationshipModel.relationship_type == relationship_type)
        if status:
            stmt = stmt.where(DetectedRelationshipModel.status == status)
        if source_id:
            stmt = stmt.where(DetectedRelationshipModel.source_id == source_id)
        if target_id:
            stmt = stmt.where(DetectedRelationshipModel.target_id == target_id)
        if detection_run_id:
            stmt = stmt.where(DetectedRelationshipModel.detection_run_id == detection_run_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar() or 0

        stmt = stmt.order_by(DetectedRelationshipModel.created_at.desc()).offset(skip).limit(limit)
        models = self.session.execute(stmt).scalars().all()

        domain_rels = [self._to_domain(m, []) for m in models]
        return domain_rels, total

    def save_review(self, review: RelationshipReviewRecord) -> None:
        """Persist a human review decision and update relationship status."""
        rev_model = RelationshipReviewModel(
            id=review.id,
            case_id=review.case_id,
            relationship_id=review.relationship_id,
            decision=review.decision.value,
            reviewer_id=review.reviewer_id,
            reason=review.reason,
            reviewed_at=review.reviewed_at,
            previous_status=review.previous_status.value,
            new_status=review.new_status.value,
        )
        self.session.add(rev_model)

        # Update detected relationship table status and status determination method
        rel_model = self.session.get(DetectedRelationshipModel, review.relationship_id)
        if rel_model:
            rel_model.status = review.new_status.value
            rel_model.status_determination_method = StatusDeterminationMethod.HUMAN_REVIEW.value
            rel_model.status_rationale = f"{rel_model.status_rationale} [Human Review: {review.decision.value} by {review.reviewer_id}: {review.reason}]"
            rel_model.updated_at = review.reviewed_at

        self.session.flush()

    def list_reviews_for_relationship(
        self, case_id: str, relationship_id: str
    ) -> list[RelationshipReviewRecord]:
        """List all review history decisions for a relationship in chronological order."""
        stmt = (
            select(RelationshipReviewModel)
            .where(
                RelationshipReviewModel.case_id == case_id,
                RelationshipReviewModel.relationship_id == relationship_id,
            )
            .order_by(RelationshipReviewModel.reviewed_at.asc())
        )
        models = self.session.execute(stmt).scalars().all()
        return [
            RelationshipReviewRecord(
                id=m.id,
                relationship_id=m.relationship_id,
                case_id=m.case_id,
                decision=RelationshipReviewAction(m.decision),
                reviewer_id=m.reviewer_id,
                reason=m.reason,
                reviewed_at=m.reviewed_at,
                previous_status=RelationshipStatus(m.previous_status),
                new_status=RelationshipStatus(m.new_status),
            )
            for m in models
        ]

    def _to_domain(
        self, model: DetectedRelationshipModel, reviews: list[RelationshipReviewRecord]
    ) -> DetectedRelationship:
        evidence_dict = model.evidence_payload or {}
        evidence = RelationshipEvidence(**evidence_dict)

        ontology_ver = getattr(model, "ontology_version", "2.0") or "2.0"
        legacy_type = getattr(model, "legacy_relationship_type", None)
        status_det_raw = getattr(model, "status_determination_method", "EVIDENTIARY_RULE")
        status_det = (
            StatusDeterminationMethod(status_det_raw)
            if status_det_raw in [e.value for e in StatusDeterminationMethod]
            else StatusDeterminationMethod.EVIDENTIARY_RULE
        )
        dup_kind_raw = getattr(model, "duplicate_kind", None)
        dup_kind = (
            DuplicateKind(dup_kind_raw)
            if dup_kind_raw in [e.value for e in DuplicateKind]
            else None
        )

        return DetectedRelationship(
            id=model.id,
            case_id=model.case_id,
            detection_run_id=model.detection_run_id,
            relationship_type=RelationshipType(model.relationship_type),
            ontology_version=ontology_ver,
            legacy_relationship_type=legacy_type,
            source_id=model.source_id,
            source_type=model.source_type,
            source_label=model.source_label,
            target_id=model.target_id,
            target_type=model.target_type,
            target_label=model.target_label,
            direction_display=model.direction_display,
            status=RelationshipStatus(model.status),
            status_determination_method=status_det,
            duplicate_kind=dup_kind,
            score=model.score,
            score_semantics=model.score_semantics,
            detection_method=RelationshipDetectionMethod(model.detection_method),
            detection_version=model.detection_version,
            status_rationale=model.status_rationale,
            evidence=evidence,
            is_human_reviewed=len(reviews) > 0,
            human_review_status=reviews[-1].decision.value if reviews else None,
            review_history=reviews,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
