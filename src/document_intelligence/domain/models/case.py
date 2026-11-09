"""Case entity representing an investigation workspace with lifecycle invariants."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.core.exceptions import InvalidStatusTransitionException
from document_intelligence.domain.enums import CaseStatus
from document_intelligence.domain.identifiers import generate_case_reference, generate_id, utc_now

# Explicit allowed state transitions
ALLOWED_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.DRAFT: {CaseStatus.ACTIVE, CaseStatus.ARCHIVED},
    CaseStatus.ACTIVE: {CaseStatus.UNDER_REVIEW, CaseStatus.ARCHIVED},
    CaseStatus.UNDER_REVIEW: {CaseStatus.ACTIVE, CaseStatus.COMPLETED, CaseStatus.ARCHIVED},
    CaseStatus.COMPLETED: {CaseStatus.UNDER_REVIEW, CaseStatus.ARCHIVED},
    CaseStatus.ARCHIVED: {CaseStatus.ACTIVE},  # Reopen to active
}


class Case(BaseModel):
    """Case aggregate root representing a forensic investigation workspace."""

    id: str = Field(default_factory=generate_id)
    case_reference: str = Field(default_factory=generate_case_reference)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    status: CaseStatus = Field(default=CaseStatus.DRAFT)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def can_transition_to(self, target_status: CaseStatus) -> bool:
        """Check whether transition to target_status is permitted."""
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        return target_status in allowed

    def transition_to(self, target_status: CaseStatus) -> None:
        """Transition case to a new lifecycle state enforcing business rules."""
        if target_status == self.status:
            return

        if not self.can_transition_to(target_status):
            raise InvalidStatusTransitionException(
                entity="Case",
                current_status=self.status.value,
                target_status=target_status.value,
            )

        self.status = target_status
        self.updated_at = utc_now()
