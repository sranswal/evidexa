"""ReviewDecision entity capturing human investigator evaluations."""

from datetime import datetime

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import FindingStatus, ReviewDecisionType
from document_intelligence.domain.identifiers import generate_id, utc_now


class ReviewDecision(BaseModel):
    """Human review record for a specific finding."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    finding_id: str
    reviewer_id: str = Field(min_length=1, max_length=100)
    decision: ReviewDecisionType
    comment: str = Field(min_length=1, max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)
    previous_status: FindingStatus
    new_status: FindingStatus
