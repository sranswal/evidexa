"""Schemas defining standard input parameters for forensic analyzers."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AnalyzerInput(BaseModel):
    """Normalized input payload passed to any ForensicAnalyzer implementation."""

    document_id: str
    case_id: str
    processing_run_id: str
    file_path: Path
    document_sha256: str
    declared_media_type: str = "application/pdf"
    detected_media_type: str = "application/pdf"
    options: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=30.0, gt=0.0)
