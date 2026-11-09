"""SQLAlchemy repository for entity candidate matches and human review decisions."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    EntityMatchClassification,
    EntityMatchingMethod,
    EntityReviewAction,
    HumanReviewStatus,
    MatchDecisionStatus,
    ResolvedEntityType,
)
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMatchEvidence,
    HumanMatchReview,
)
from document_intelligence.infrastructure.persistence.models import (
    EntityCandidateMatchModel,
    EntityMatchReviewModel,
)


class EntityMatchRepository:
    """Provides relational persistence for entity candidate matches and review history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_match(self, match: EntityCandidateMatch) -> None:
        """Upsert an entity candidate match."""
        model = self.session.get(EntityCandidateMatchModel, match.id)
        if model is None:
            model = EntityCandidateMatchModel(
                id=match.id,
                case_id=match.case_id,
                processing_run_id=match.processing_run_id,
                entity_type=match.entity_type.value,
                target_mention_id=match.target_mention_id,
                candidate_mention_id=match.candidate_mention_id,
                target_value_display=match.target_value_display,
                candidate_value_display=match.candidate_value_display,
                matching_method=match.matching_method.value,
                match_classification=match.match_classification.value,
                match_score=match.match_score,
                score_semantics=match.score_semantics,
                decision_status=match.decision_status.value,
                review_status=match.review_status.value,
                evidence_payload=match.evidence.model_dump(),
                created_at=match.created_at,
            )
            self.session.add(model)
        else:
            model.decision_status = match.decision_status.value
            model.review_status = match.review_status.value
            model.match_score = match.match_score
            model.match_classification = match.match_classification.value
            model.evidence_payload = match.evidence.model_dump()

        self.session.flush()

    def save_matches(self, matches: list[EntityCandidateMatch]) -> None:
        """Batch save candidate matches."""
        for m in matches:
            self.save_match(m)
        self.session.flush()

    def get_match_by_id(self, case_id: str, match_id: str) -> EntityCandidateMatch | None:
        """Retrieve match by ID, ensuring case isolation."""
        stmt = select(EntityCandidateMatchModel).where(
            EntityCandidateMatchModel.case_id == case_id,
            EntityCandidateMatchModel.id == match_id,
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        if model is None:
            return None

        reviews = self.list_reviews_for_match(case_id, match_id)
        return self._to_domain(model, reviews)

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
        """List and paginate candidate matches with filtering."""
        stmt = select(EntityCandidateMatchModel).where(EntityCandidateMatchModel.case_id == case_id)

        if entity_type:
            stmt = stmt.where(EntityCandidateMatchModel.entity_type == entity_type)
        if classification:
            stmt = stmt.where(EntityCandidateMatchModel.match_classification == classification)
        if decision_status:
            stmt = stmt.where(EntityCandidateMatchModel.decision_status == decision_status)
        if review_status:
            stmt = stmt.where(EntityCandidateMatchModel.review_status == review_status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar() or 0

        stmt = stmt.order_by(EntityCandidateMatchModel.created_at.desc()).offset(skip).limit(limit)
        models = self.session.execute(stmt).scalars().all()

        domain_matches = [self._to_domain(m, []) for m in models]
        return domain_matches, total

    def save_review(self, review: HumanMatchReview) -> None:
        """Persist a human match review decision and update candidate match status."""
        rev_model = EntityMatchReviewModel(
            id=review.id,
            case_id=review.case_id,
            match_id=review.match_id,
            decision=review.decision.value,
            reviewer_id=review.reviewer_id,
            reason=review.reason,
            reviewed_at=review.reviewed_at,
            previous_status=review.previous_status.value,
            new_status=review.new_status.value,
        )
        self.session.add(rev_model)

        # Update candidate match table status
        match_model = self.session.get(EntityCandidateMatchModel, review.match_id)
        if match_model:
            match_model.decision_status = review.new_status.value
            if review.decision == EntityReviewAction.CONFIRM_MATCH:
                match_model.review_status = HumanReviewStatus.CONFIRMED.value
            elif review.decision == EntityReviewAction.REJECT_MATCH:
                match_model.review_status = HumanReviewStatus.REJECTED.value
            else:
                match_model.review_status = HumanReviewStatus.AMBIGUOUS.value

        self.session.flush()

    def list_reviews_for_match(self, case_id: str, match_id: str) -> list[HumanMatchReview]:
        """List all review history decisions for a match in chronological order."""
        stmt = (
            select(EntityMatchReviewModel)
            .where(
                EntityMatchReviewModel.case_id == case_id,
                EntityMatchReviewModel.match_id == match_id,
            )
            .order_by(EntityMatchReviewModel.reviewed_at.asc())
        )
        models = self.session.execute(stmt).scalars().all()
        return [
            HumanMatchReview(
                id=m.id,
                match_id=m.match_id,
                case_id=m.case_id,
                decision=EntityReviewAction(m.decision),
                reviewer_id=m.reviewer_id,
                reason=m.reason,
                reviewed_at=m.reviewed_at,
                previous_status=MatchDecisionStatus(m.previous_status),
                new_status=MatchDecisionStatus(m.new_status),
            )
            for m in models
        ]

    def _to_domain(
        self, model: EntityCandidateMatchModel, reviews: list[HumanMatchReview]
    ) -> EntityCandidateMatch:
        evidence_dict = model.evidence_payload or {}
        evidence = EntityMatchEvidence(**evidence_dict)

        return EntityCandidateMatch(
            id=model.id,
            case_id=model.case_id,
            processing_run_id=model.processing_run_id,
            entity_type=ResolvedEntityType(model.entity_type),
            target_mention_id=model.target_mention_id,
            candidate_mention_id=model.candidate_mention_id,
            target_value_display=model.target_value_display,
            candidate_value_display=model.candidate_value_display,
            matching_method=EntityMatchingMethod(model.matching_method),
            match_classification=EntityMatchClassification(model.match_classification),
            match_score=model.match_score,
            score_semantics=model.score_semantics,
            decision_status=MatchDecisionStatus(model.decision_status),
            review_status=HumanReviewStatus(model.review_status),
            evidence=evidence,
            review_history=reviews,
            created_at=model.created_at,
        )
