"""InvestigationDossier entity and section value objects representing formal case reports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.core.exceptions import ValidationException
from document_intelligence.domain.enums import (
    DossierStatus,
)
from document_intelligence.domain.identifiers import generate_id, utc_now


class DossierSection(BaseModel):
    """Structured chapter or section within an investigation dossier."""

    section_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    order: int = Field(ge=1)
    content: str = Field(default="")
    items: list[dict[str, Any]] = Field(default_factory=list)


class DossierFinding(BaseModel):
    """Snapshot representation of an aggregated finding embedded within a dossier."""

    id: str
    source_type: str
    source_id: str
    category: str
    evidentiary_classification: str
    source_status: str
    review_status: str
    title: str
    description: str
    explanation: str
    severity: str
    affected_document_ids: list[str] = Field(default_factory=list)
    affected_entity_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    is_reviewed: bool = False
    review_history: list[dict[str, Any]] = Field(default_factory=list)


class InvestigationDossier(BaseModel):
    """Investigation Dossier summarizing evidence, findings, and review status.

    NOTE: A dossier is a structured investigation artifact, NOT an automated fraud verdict or legal conclusion.
    """

    id: str = Field(default_factory=generate_id)
    case_id: str
    title: str = Field(default="Investigation Evidence Dossier", max_length=255)
    scope_and_purpose: str = Field(
        default="Digital forensics and document intelligence evidentiary inquiry",
        max_length=2000,
    )
    version: int = Field(default=1, ge=1)
    status: DossierStatus = Field(default=DossierStatus.DRAFT)
    executive_summary: str = Field(min_length=1, max_length=10000)
    sections: list[DossierSection] = Field(default_factory=list)
    document_summaries: list[dict[str, Any]] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    review_decisions: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    dossier_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str = Field(min_length=1, max_length=100)
    finalized_at: datetime | None = None

    def approve(self) -> None:
        """Approve and finalize dossier."""
        if self.status == DossierStatus.APPROVED:
            return
        if self.status not in (DossierStatus.PENDING_REVIEW, DossierStatus.DRAFT):
            raise ValidationException(
                f"Cannot approve dossier with status '{self.status.value}'. Must be in DRAFT or PENDING_REVIEW."
            )
        self.status = DossierStatus.APPROVED
        self.finalized_at = utc_now()

    def finalize(self, content_hash: str, snapshot_payload: dict[str, Any]) -> None:
        """Finalize and freeze dossier into an immutable approved state."""
        if self.status == DossierStatus.APPROVED:
            return
        if self.status not in (DossierStatus.PENDING_REVIEW, DossierStatus.DRAFT):
            raise ValidationException(
                f"Cannot finalize dossier with status '{self.status.value}'. Must be in DRAFT or PENDING_REVIEW."
            )
        self.status = DossierStatus.APPROVED
        self.content_hash = content_hash
        self.dossier_payload = snapshot_payload
        self.finalized_at = utc_now()

    def create_next_version(self, created_by: str) -> InvestigationDossier:
        """Generate a new draft version from this dossier, superseding this one."""
        self.status = DossierStatus.SUPERSEDED

        return InvestigationDossier(
            case_id=self.case_id,
            title=self.title,
            scope_and_purpose=self.scope_and_purpose,
            version=self.version + 1,
            status=DossierStatus.DRAFT,
            executive_summary=self.executive_summary,
            sections=list(self.sections),
            document_summaries=list(self.document_summaries),
            finding_ids=list(self.finding_ids),
            evidence_ids=list(self.evidence_ids),
            review_decisions=list(self.review_decisions),
            limitations=list(self.limitations),
            unresolved_questions=list(self.unresolved_questions),
            created_by=created_by,
        )
