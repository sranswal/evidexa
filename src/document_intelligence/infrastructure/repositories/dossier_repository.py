"""SQLAlchemy repository for investigation evidence dossiers and aggregated finding reviews."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    DossierStatus,
    InvestigatorReviewAction,
)
from document_intelligence.domain.models.aggregated_finding import AggregatedFindingReview
from document_intelligence.domain.models.investigation_dossier import (
    DossierSection,
    InvestigationDossier,
)
from document_intelligence.infrastructure.persistence.models import (
    AggregatedFindingReviewModel,
    InvestigationDossierModel,
)


class DossierRepository:
    """Provides relational persistence for investigation dossiers and reviewer decision history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_dossier(self, dossier: InvestigationDossier) -> InvestigationDossier:
        """Upsert an InvestigationDossier record."""
        model = self.session.get(InvestigationDossierModel, dossier.id)

        sections_payload = [s.model_dump(mode="json") for s in dossier.sections]

        if model is None:
            model = InvestigationDossierModel(
                id=dossier.id,
                case_id=dossier.case_id,
                title=dossier.title,
                scope_and_purpose=dossier.scope_and_purpose,
                version=dossier.version,
                status=dossier.status.value,
                executive_summary=dossier.executive_summary,
                document_summaries=dossier.document_summaries,
                finding_ids=dossier.finding_ids,
                evidence_ids=dossier.evidence_ids,
                review_decisions=dossier.review_decisions,
                limitations=dossier.limitations,
                unresolved_questions=dossier.unresolved_questions,
                sections=sections_payload,
                content_hash=dossier.content_hash,
                dossier_payload=dossier.dossier_payload,
                created_at=dossier.created_at,
                created_by=dossier.created_by,
                finalized_at=dossier.finalized_at,
            )
            self.session.add(model)
        else:
            model.title = dossier.title
            model.scope_and_purpose = dossier.scope_and_purpose
            model.status = dossier.status.value
            model.executive_summary = dossier.executive_summary
            model.document_summaries = dossier.document_summaries
            model.finding_ids = dossier.finding_ids
            model.evidence_ids = dossier.evidence_ids
            model.review_decisions = dossier.review_decisions
            model.limitations = dossier.limitations
            model.unresolved_questions = dossier.unresolved_questions
            model.sections = sections_payload
            model.content_hash = dossier.content_hash
            model.dossier_payload = dossier.dossier_payload
            model.finalized_at = dossier.finalized_at

        self.session.flush()
        return dossier

    def get_by_id(self, dossier_id: str) -> InvestigationDossier | None:
        """Retrieve dossier by ID across cases."""
        model = self.session.get(InvestigationDossierModel, dossier_id)
        if not model:
            return None
        return self._to_domain_dossier(model)

    def list_by_case(self, case_id: str) -> list[InvestigationDossier]:
        """List all dossiers for a case."""
        return self.list_dossiers_for_case(case_id)

    def add_aggregated_review(self, review: AggregatedFindingReview) -> AggregatedFindingReview:
        """Persist an append-only investigator review decision."""
        self.save_aggregated_review(review)
        return review

    def list_aggregated_reviews(self, case_id: str) -> list[AggregatedFindingReview]:
        """List all investigator review decisions recorded for a case."""
        return self.list_all_reviews_for_case(case_id)

    def get_dossier_by_id(self, case_id: str, dossier_id: str) -> InvestigationDossier | None:
        """Retrieve dossier by ID strictly bounded to a case."""
        stmt = (
            select(InvestigationDossierModel)
            .where(InvestigationDossierModel.case_id == case_id)
            .where(InvestigationDossierModel.id == dossier_id)
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return self._to_domain_dossier(model)

    def get_dossier_by_version(self, case_id: str, version: int) -> InvestigationDossier | None:
        """Retrieve dossier by version for a case."""
        stmt = (
            select(InvestigationDossierModel)
            .where(InvestigationDossierModel.case_id == case_id)
            .where(InvestigationDossierModel.version == version)
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return self._to_domain_dossier(model)

    def list_dossiers_for_case(self, case_id: str) -> list[InvestigationDossier]:
        """List all dossier versions for a case in descending version order."""
        stmt = (
            select(InvestigationDossierModel)
            .where(InvestigationDossierModel.case_id == case_id)
            .order_by(desc(InvestigationDossierModel.version))
        )
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain_dossier(m) for m in models]

    def get_latest_dossier(self, case_id: str) -> InvestigationDossier | None:
        """Retrieve the most recent dossier version for a case."""
        stmt = (
            select(InvestigationDossierModel)
            .where(InvestigationDossierModel.case_id == case_id)
            .order_by(desc(InvestigationDossierModel.version))
            .limit(1)
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return self._to_domain_dossier(model)

    def save_aggregated_review(self, review: AggregatedFindingReview) -> None:
        """Persist an append-only investigator review decision."""
        model = AggregatedFindingReviewModel(
            id=review.id,
            case_id=review.case_id,
            finding_id=review.finding_id,
            action=review.action.value,
            reviewer_id=review.reviewer_id,
            comment=review.comment,
            reviewed_at=review.reviewed_at,
            previous_status=review.previous_status,
            new_status=review.new_status,
        )
        self.session.add(model)
        self.session.flush()

    def list_reviews_for_finding(
        self, case_id: str, finding_id: str
    ) -> list[AggregatedFindingReview]:
        """List review decisions for a specific finding in chronological order."""
        stmt = (
            select(AggregatedFindingReviewModel)
            .where(AggregatedFindingReviewModel.case_id == case_id)
            .where(AggregatedFindingReviewModel.finding_id == finding_id)
            .order_by(AggregatedFindingReviewModel.reviewed_at.asc())
        )
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain_review(m) for m in models]

    def list_all_reviews_for_case(self, case_id: str) -> list[AggregatedFindingReview]:
        """List all investigator review decisions recorded for a case."""
        stmt = (
            select(AggregatedFindingReviewModel)
            .where(AggregatedFindingReviewModel.case_id == case_id)
            .order_by(AggregatedFindingReviewModel.reviewed_at.asc())
        )
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain_review(m) for m in models]

    def _to_domain_dossier(self, model: InvestigationDossierModel) -> InvestigationDossier:
        sections_data = getattr(model, "sections", None) or []
        sections = [
            DossierSection(
                section_id=s.get("section_id", "sec-1"),
                title=s.get("title", ""),
                order=s.get("order", 1),
                content=s.get("content", ""),
                items=s.get("items", []),
            )
            for s in sections_data
        ]

        return InvestigationDossier(
            id=model.id,
            case_id=model.case_id,
            title=getattr(model, "title", "Investigation Evidence Dossier"),
            scope_and_purpose=getattr(model, "scope_and_purpose", ""),
            version=model.version,
            status=DossierStatus(model.status),
            executive_summary=model.executive_summary,
            sections=sections,
            document_summaries=model.document_summaries or [],
            finding_ids=model.finding_ids or [],
            evidence_ids=model.evidence_ids or [],
            review_decisions=model.review_decisions or [],
            limitations=model.limitations or [],
            unresolved_questions=getattr(model, "unresolved_questions", None) or [],
            content_hash=getattr(model, "content_hash", None),
            dossier_payload=getattr(model, "dossier_payload", None) or {},
            created_at=model.created_at,
            created_by=model.created_by,
            finalized_at=model.finalized_at,
        )

    def _to_domain_review(self, model: AggregatedFindingReviewModel) -> AggregatedFindingReview:
        return AggregatedFindingReview(
            id=model.id,
            case_id=model.case_id,
            finding_id=model.finding_id,
            action=InvestigatorReviewAction(model.action),
            reviewer_id=model.reviewer_id,
            comment=model.comment,
            reviewed_at=model.reviewed_at,
            previous_status=model.previous_status,
            new_status=model.new_status,
        )
