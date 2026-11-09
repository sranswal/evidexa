"""ProcessingRun entity tracking execution of analysis and forensic pipelines."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.domain.identifiers import generate_id, utc_now


class ProcessingRun(BaseModel):
    """Represents a discrete pipeline execution over one or more documents."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    document_ids: list[str] = Field(min_length=1)
    pipeline_name: str = Field(min_length=1, max_length=100)
    pipeline_version: str = Field(min_length=1, max_length=50)
    status: PipelineStatus = Field(default=PipelineStatus.QUEUED)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    snapshot_sha256: str | None = Field(default=None, max_length=64)
    error_code: str | None = Field(default=None, max_length=50)
    error_message: str | None = Field(default=None, max_length=2000)
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)
    resource_metrics: dict[str, Any] | None = None

    def mark_succeeded(self) -> None:
        """Mark run as succeeded with UTC completion time."""
        self.status = PipelineStatus.SUCCEEDED
        self.completed_at = utc_now()

    def mark_failed(self, error_code: str, error_message: str) -> None:
        """Mark run as failed with sanitized error details."""
        self.status = PipelineStatus.FAILED
        self.completed_at = utc_now()
        self.error_code = error_code
        self.error_message = error_message[:2000]
