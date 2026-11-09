"""InvestigationDossier entity representing formal structured case reports."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.core.exceptions import ValidationException
from document_intelligence.domain.enums import DossierStatus
from document_intelligence.domain.identifiers import generate_id, utc_now


class InvestigationDossier(BaseModel):
    """Investigation Dossier summarizing evidence, findings, and review status."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    version: int = Field(default=1, ge=1)
    status: DossierStatus = Field(default=DossierStatus.DRAFT)
    executive_summary: str = Field(min_length=1, max_length=10000)
    document_summaries: list[dict[str, Any]] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    review_decisions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str = Field(min_length=1, max_length=100)
    finalized_at: datetime | None = None

    def approve(self) -> None:
        """Approve and finalize dossier."""
        if self.status == DossierStatus.APPROVED:
            return
        if self.status != DossierStatus.PENDING_REVIEW and self.status != DossierStatus.DRAFT:
            raise ValidationException(
                f"Cannot approve dossier with status '{self.status.value}'. Must be in DRAFT or PENDING_REVIEW."
            )
        self.status = DossierStatus.APPROVED
        self.finalized_at = utc_now()

    def create_next_version(self, created_by: str) -> "InvestigationDossier":
        """Generate a new draft version from this dossier, superseding this one."""
        self.status = DossierStatus.SUPERSEDED

        return InvestigationDossier(
            case_id=self.case_id,
            version=self.version + 1,
            status=DossierStatus.DRAFT,
            executive_summary=self.executive_summary,
            document_summaries=list(self.document_summaries),
            finding_ids=list(self.finding_ids),
            evidence_ids=list(self.evidence_ids),
            review_decisions=list(self.review_decisions),
            limitations=list(self.limitations),
            created_by=created_by,
        )
