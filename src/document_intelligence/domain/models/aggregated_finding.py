"""Domain models for unified cross-domain findings aggregation and investigator review history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import (
    AggregatedFindingCategory,
    EvidentiaryClassification,
    FindingSeverity,
    InvestigatorReviewAction,
)
from document_intelligence.domain.identifiers import generate_id, utc_now


class AggregatedFindingReview(BaseModel):
    """Immutable human review record recording an investigator's evaluation."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    finding_id: str
    action: InvestigatorReviewAction
    reviewer_id: str = Field(min_length=1, max_length=100)
    comment: str = Field(min_length=1, max_length=4000)
    reviewed_at: datetime = Field(default_factory=utc_now)
    previous_status: str
    new_status: str

    def __init__(
        self,
        *,
        id: str | None = None,
        case_id: str,
        finding_id: str,
        action: InvestigatorReviewAction,
        reviewer_id: str,
        comment: str | None = None,
        rationale: str | None = None,
        reviewed_at: datetime | None = None,
        created_at: datetime | None = None,
        previous_status: str | None = None,
        prior_status: str | None = None,
        new_status: str,
        **data: Any,
    ) -> None:
        actual_comment = comment or rationale or ""
        actual_prev = previous_status or prior_status or "UNREVIEWED"
        actual_reviewed_at = reviewed_at or created_at or utc_now()
        actual_id = id or generate_id()
        super().__init__(
            id=actual_id,
            case_id=case_id,
            finding_id=finding_id,
            action=action,
            reviewer_id=reviewer_id,
            comment=actual_comment,
            reviewed_at=actual_reviewed_at,
            previous_status=actual_prev,
            new_status=new_status,
            **data,
        )

    @property
    def rationale(self) -> str:
        return self.comment

    @property
    def prior_status(self) -> str:
        return self.previous_status

    @property
    def created_at(self) -> datetime:
        return self.reviewed_at


class AggregatedFinding(BaseModel):
    """Unified investigation finding aggregating forensic, consistency, and relational observations.

    NOTE: An aggregated finding represents an evidentiary observation or anomaly, NOT a judicial fraud verdict.
    """

    id: str = Field(default_factory=generate_id)
    case_id: str
    source_type: str = Field(
        description="Originating subsystem (e.g. FORENSIC_FINDING, CONSISTENCY_FINDING, RELATIONSHIP_ANOMALY, ENTITY_IDENTITY_CONFLICT)."
    )
    source_id: str = Field(description="Primary key in underlying authoritative source table.")
    category: AggregatedFindingCategory
    evidentiary_classification: EvidentiaryClassification
    source_status: str
    review_status: str = Field(default="UNREVIEWED")
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    explanation: str = Field(default="", max_length=4000)
    severity: FindingSeverity
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    affected_document_ids: list[str] = Field(default_factory=list)
    affected_entity_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    is_reviewed: bool = False
    review_history: list[AggregatedFindingReview] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
