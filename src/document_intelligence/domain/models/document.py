"""Document entity representing an original uploaded evidence item."""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from document_intelligence.domain.enums import DocumentType, IngestionStatus
from document_intelligence.domain.identifiers import generate_id, utc_now


class Document(BaseModel):
    """Document entity holding immutable original metadata and storage reference."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=100)
    file_extension: str = Field(min_length=1, max_length=20)
    file_size_bytes: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)
    storage_key: str = Field(min_length=1, max_length=500)
    page_count: int | None = Field(default=None, ge=1)
    document_type: DocumentType | None = Field(default=DocumentType.UNKNOWN)
    ingestion_status: IngestionStatus = Field(default=IngestionStatus.STORED)
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sha256")
    @classmethod
    def validate_sha256_format(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise ValueError("Document SHA-256 must be a 64-character hexadecimal string.")
        return value.lower()
