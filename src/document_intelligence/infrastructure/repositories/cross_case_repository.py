"""Repository for persisting cross-case scopes, candidate correlation matches, and review records."""

from __future__ import annotations

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from document_intelligence.domain.identifiers import utc_now
from document_intelligence.infrastructure.persistence.models import (
    CrossCaseCandidateMatchModel,
    CrossCaseCandidateReviewModel,
    CrossCaseScopeModel,
)


class CrossCaseRepository:
    """SQLAlchemy repository for cross-case correlation entities."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Investigation Scopes
    # -------------------------------------------------------------------------

    def create_scope(self, scope: CrossCaseScopeModel) -> CrossCaseScopeModel:
        """Persist a new cross-case investigation scope."""
        self.db.add(scope)
        self.db.commit()
        self.db.refresh(scope)
        return scope

    def get_scope(self, scope_id: str) -> CrossCaseScopeModel | None:
        """Retrieve a cross-case scope by its unique ID."""
        return self.db.get(CrossCaseScopeModel, scope_id)

    def list_scopes(
        self, organization_id: str, is_active: bool | None = True
    ) -> list[CrossCaseScopeModel]:
        """List scopes belonging to an organization."""
        stmt = select(CrossCaseScopeModel).where(
            CrossCaseScopeModel.organization_id == organization_id
        )
        if is_active is not None:
            stmt = stmt.where(CrossCaseScopeModel.is_active == is_active)
        stmt = stmt.order_by(desc(CrossCaseScopeModel.created_at))
        return list(self.db.scalars(stmt).all())

    def update_scope(self, scope: CrossCaseScopeModel) -> CrossCaseScopeModel:
        """Update existing scope metadata and timestamps."""
        scope.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(scope)
        return scope

    def delete_scope(self, scope_id: str) -> bool:
        """Remove a scope and cascade its matches and reviews."""
        scope = self.get_scope(scope_id)
        if not scope:
            return False
        self.db.delete(scope)
        self.db.commit()
        return True

    # -------------------------------------------------------------------------
    # Candidate Correlation Matches
    # -------------------------------------------------------------------------

    def save_candidate_matches(
        self, matches: list[CrossCaseCandidateMatchModel]
    ) -> list[CrossCaseCandidateMatchModel]:
        """Bulk persist generated candidate matches."""
        if not matches:
            return []
        self.db.add_all(matches)
        self.db.commit()
        for m in matches:
            self.db.refresh(m)
        return matches

    def clear_scope_matches(self, scope_id: str) -> None:
        """Clear existing unreviewed candidate matches for a scope before re-running."""
        stmt = delete(CrossCaseCandidateMatchModel).where(
            CrossCaseCandidateMatchModel.scope_id == scope_id,
            CrossCaseCandidateMatchModel.decision_status == "PENDING_REVIEW",
        )
        self.db.execute(stmt)
        self.db.commit()

    def list_candidate_matches(
        self,
        scope_id: str,
        decision_status: str | None = None,
        entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CrossCaseCandidateMatchModel], int]:
        """Retrieve paginated candidate matches for a scope with optional status/type filter."""
        stmt = select(CrossCaseCandidateMatchModel).where(
            CrossCaseCandidateMatchModel.scope_id == scope_id
        )
        if decision_status:
            stmt = stmt.where(CrossCaseCandidateMatchModel.decision_status == decision_status)
        if entity_type:
            stmt = stmt.where(CrossCaseCandidateMatchModel.entity_type == entity_type)

        # Count total
        from sqlalchemy import func

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        # Paginate
        stmt = (
            stmt.order_by(desc(CrossCaseCandidateMatchModel.match_score))
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all()), total

    def get_candidate_match(self, match_id: str) -> CrossCaseCandidateMatchModel | None:
        """Retrieve an individual candidate match by ID."""
        return self.db.get(CrossCaseCandidateMatchModel, match_id)

    def update_match_status(
        self, match: CrossCaseCandidateMatchModel, new_status: str
    ) -> CrossCaseCandidateMatchModel:
        """Update decision status of a candidate match."""
        match.decision_status = new_status
        self.db.commit()
        self.db.refresh(match)
        return match

    # -------------------------------------------------------------------------
    # Candidate Reviews
    # -------------------------------------------------------------------------

    def save_review(self, review: CrossCaseCandidateReviewModel) -> CrossCaseCandidateReviewModel:
        """Persist an investigator review decision."""
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def list_reviews_for_match(self, match_id: str) -> list[CrossCaseCandidateReviewModel]:
        """Retrieve chronological review history for a candidate match."""
        stmt = (
            select(CrossCaseCandidateReviewModel)
            .where(CrossCaseCandidateReviewModel.match_id == match_id)
            .order_by(CrossCaseCandidateReviewModel.reviewed_at)
        )
        return list(self.db.scalars(stmt).all())

    def list_reviews_for_scope(self, scope_id: str) -> list[CrossCaseCandidateReviewModel]:
        """Retrieve all reviews conducted within a scope."""
        stmt = (
            select(CrossCaseCandidateReviewModel)
            .where(CrossCaseCandidateReviewModel.scope_id == scope_id)
            .order_by(desc(CrossCaseCandidateReviewModel.reviewed_at))
        )
        return list(self.db.scalars(stmt).all())
