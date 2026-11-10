"""SQLAlchemy repository for cross-document consistency findings and human review audit trail."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    ConsistencyDetectionMethod,
    ConsistencyOutcome,
    ConsistencyReviewAction,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from document_intelligence.domain.identifiers import utc_now
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.consistency import (
    ConsistencyComparison,
    ConsistencyEvidenceLocation,
    ConsistencyFinding,
    ConsistencyReview,
)
from document_intelligence.infrastructure.persistence.models import (
    ConsistencyFindingModel,
    ConsistencyReviewModel,
)


class ConsistencyRepository:
    """Provides relational persistence for cross-document consistency findings and review records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_finding(self, finding: ConsistencyFinding) -> None:
        """Upsert a consistency finding."""
        model = self.session.get(ConsistencyFindingModel, finding.id)

        locations_dicts = [loc.model_dump(mode="json") for loc in finding.locations]
        comparisons_dicts = [comp.model_dump(mode="json") for comp in finding.comparisons]

        if model is None:
            model = ConsistencyFindingModel(
                id=finding.id,
                case_id=finding.case_id,
                analysis_run_id=finding.analysis_run_id,
                rule_id=finding.rule_id,
                rule_version=finding.rule_version,
                category=finding.category.value
                if hasattr(finding.category, "value")
                else str(finding.category),
                title=finding.title,
                explanation=finding.explanation,
                severity=finding.severity.value
                if hasattr(finding.severity, "value")
                else str(finding.severity),
                outcome=finding.outcome.value
                if hasattr(finding.outcome, "value")
                else str(finding.outcome),
                score=finding.score,
                score_semantics=finding.score_semantics,
                affected_document_ids=finding.affected_document_ids,
                compared_fields=finding.compared_fields,
                original_values=finding.original_values,
                normalized_values=finding.normalized_values,
                supporting_evidence_ids=finding.supporting_evidence_ids,
                contradicting_evidence_ids=finding.contradicting_evidence_ids,
                locations_payload=locations_dicts,
                detection_method=finding.detection_method.value
                if hasattr(finding.detection_method, "value")
                else str(finding.detection_method),
                rule_parameters=finding.rule_parameters,
                limitations=finding.limitations,
                status=finding.status.value
                if hasattr(finding.status, "value")
                else str(finding.status),
                review_status=finding.review_status,
                is_human_reviewed=finding.is_human_reviewed,
                comparisons_payload=comparisons_dicts,
                created_at=finding.created_at,
                updated_at=finding.updated_at,
            )
            self.session.add(model)
        else:
            model.status = (
                finding.status.value if hasattr(finding.status, "value") else str(finding.status)
            )
            model.review_status = finding.review_status
            model.is_human_reviewed = finding.is_human_reviewed
            model.updated_at = utc_now()

        self.session.flush()

    def save_findings(self, findings: list[ConsistencyFinding]) -> None:
        """Batch save consistency findings."""
        for finding in findings:
            self.save_finding(finding)

    def get_finding(self, finding_id: str, case_id: str) -> ConsistencyFinding | None:
        """Retrieve a finding by ID strictly bounded to a case."""
        stmt = (
            select(ConsistencyFindingModel)
            .where(ConsistencyFindingModel.id == finding_id)
            .where(ConsistencyFindingModel.case_id == case_id)
        )
        model = self.session.execute(stmt).scalars().first()
        if not model:
            return None
        reviews = self.list_reviews_for_finding(finding_id, case_id)
        return self._to_domain_finding(model, reviews)

    def list_findings(
        self,
        case_id: str,
        run_id: str | None = None,
        rule_id: str | None = None,
        outcome: str | None = None,
        status: str | None = None,
        document_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConsistencyFinding]:
        """List findings matching filters with case-level boundary enforcement."""
        stmt = (
            select(ConsistencyFindingModel)
            .where(ConsistencyFindingModel.case_id == case_id)
            .order_by(ConsistencyFindingModel.created_at.desc())
        )

        if run_id:
            stmt = stmt.where(ConsistencyFindingModel.analysis_run_id == run_id)
        if rule_id:
            stmt = stmt.where(ConsistencyFindingModel.rule_id == rule_id)
        if outcome:
            stmt = stmt.where(ConsistencyFindingModel.outcome == outcome)
        if status:
            stmt = stmt.where(ConsistencyFindingModel.status == status)

        stmt = stmt.offset(offset).limit(limit)
        models = self.session.execute(stmt).scalars().all()

        findings: list[ConsistencyFinding] = []
        for m in models:
            if document_id and document_id not in (m.affected_document_ids or []):
                continue
            reviews = self.list_reviews_for_finding(m.id, case_id)
            findings.append(self._to_domain_finding(m, reviews))

        return findings

    def count_findings(
        self,
        case_id: str,
        run_id: str | None = None,
        rule_id: str | None = None,
        outcome: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count findings matching filters within a case."""
        stmt = select(func.count(ConsistencyFindingModel.id)).where(
            ConsistencyFindingModel.case_id == case_id
        )

        if run_id:
            stmt = stmt.where(ConsistencyFindingModel.analysis_run_id == run_id)
        if rule_id:
            stmt = stmt.where(ConsistencyFindingModel.rule_id == rule_id)
        if outcome:
            stmt = stmt.where(ConsistencyFindingModel.outcome == outcome)
        if status:
            stmt = stmt.where(ConsistencyFindingModel.status == status)

        count = self.session.execute(stmt).scalar()
        return count or 0

    def save_review(self, review: ConsistencyReview) -> None:
        """Persist a human review record in the append-only audit trail."""
        model = ConsistencyReviewModel(
            id=review.id,
            case_id=review.case_id,
            finding_id=review.finding_id,
            decision=review.decision.value
            if hasattr(review.decision, "value")
            else str(review.decision),
            reviewer_id=review.reviewer_id,
            reason=review.reason,
            reviewed_at=review.reviewed_at,
            previous_status=review.previous_status,
            new_status=review.new_status,
        )
        self.session.add(model)
        self.session.flush()

    def list_reviews_for_finding(self, finding_id: str, case_id: str) -> list[ConsistencyReview]:
        """List review decisions for a finding ordered chronologically."""
        stmt = (
            select(ConsistencyReviewModel)
            .where(ConsistencyReviewModel.finding_id == finding_id)
            .where(ConsistencyReviewModel.case_id == case_id)
            .order_by(ConsistencyReviewModel.reviewed_at.asc())
        )
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain_review(m) for m in models]

    def _to_domain_finding(
        self, model: ConsistencyFindingModel, reviews: list[ConsistencyReview]
    ) -> ConsistencyFinding:
        """Map SQL persistence model to pure domain ConsistencyFinding entity."""
        locations: list[ConsistencyEvidenceLocation] = []
        for loc_dict in model.locations_payload or []:
            bbox = None
            if loc_dict.get("bounding_box"):
                bbox = BoundingBox.model_validate(loc_dict["bounding_box"])
            locations.append(
                ConsistencyEvidenceLocation(
                    document_id=loc_dict.get("document_id", ""),
                    field_key=loc_dict.get("field_key"),
                    page_number=loc_dict.get("page_number"),
                    bounding_box=bbox,
                    evidence_node_id=loc_dict.get("evidence_node_id"),
                    raw_value=loc_dict.get("raw_value"),
                    normalized_value=loc_dict.get("normalized_value"),
                )
            )

        comparisons: list[ConsistencyComparison] = []
        for c_dict in model.comparisons_payload or []:
            comparisons.append(
                ConsistencyComparison(
                    field_key=c_dict.get("field_key", ""),
                    source_doc_id=c_dict.get("source_doc_id", ""),
                    source_value=c_dict.get("source_value"),
                    target_doc_id=c_dict.get("target_doc_id", ""),
                    target_value=c_dict.get("target_value"),
                    comparison_type=c_dict.get("comparison_type", "FIELD_COMPARISON"),
                    outcome=ConsistencyOutcome(
                        c_dict.get("outcome", ConsistencyOutcome.INCONSISTENT.value)
                    ),
                    difference=c_dict.get("difference"),
                    explanation=c_dict.get("explanation", ""),
                )
            )

        return ConsistencyFinding(
            id=model.id,
            case_id=model.case_id,
            analysis_run_id=model.analysis_run_id,
            rule_id=model.rule_id,
            rule_version=model.rule_version,
            category=FindingCategory(model.category),
            title=model.title,
            explanation=model.explanation,
            severity=FindingSeverity(model.severity),
            outcome=ConsistencyOutcome(model.outcome),
            score=model.score,
            score_semantics=model.score_semantics,
            affected_document_ids=list(model.affected_document_ids or []),
            compared_fields=list(model.compared_fields or []),
            original_values=dict(model.original_values or {}),
            normalized_values=dict(model.normalized_values or {}),
            supporting_evidence_ids=list(model.supporting_evidence_ids or []),
            contradicting_evidence_ids=list(model.contradicting_evidence_ids or []),
            locations=locations,
            detection_method=ConsistencyDetectionMethod(model.detection_method),
            rule_parameters=dict(model.rule_parameters or {}),
            limitations=list(model.limitations or []),
            status=FindingStatus(model.status),
            review_status=model.review_status,
            is_human_reviewed=model.is_human_reviewed,
            comparisons=comparisons,
            review_history=reviews,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_domain_review(self, model: ConsistencyReviewModel) -> ConsistencyReview:
        """Map SQL persistence model to pure domain ConsistencyReview entity."""
        return ConsistencyReview(
            id=model.id,
            finding_id=model.finding_id,
            case_id=model.case_id,
            decision=ConsistencyReviewAction(model.decision),
            reviewer_id=model.reviewer_id,
            reason=model.reason,
            reviewed_at=model.reviewed_at,
            previous_status=model.previous_status,
            new_status=model.new_status,
        )
