"""AuditEvent entity for immutable append-only provenance tracking and hash chaining."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import AuditEventType, EntityType
from document_intelligence.domain.identifiers import generate_id, utc_now


def canonicalize_payload(payload: dict[str, Any]) -> str:
    """Produce deterministic canonical JSON string for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def normalize_timestamp_str(dt: datetime) -> str:
    """Produce standard UTC ISO string invariant across SQLite naive/aware roundtrips."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


class AuditEvent(BaseModel):
    """Immutable audit record linked cryptographically to the preceding event."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    sequence_number: int = Field(default=1, ge=1)
    actor_id: str | None = Field(default=None, max_length=100)
    event_type: AuditEventType
    entity_type: EntityType
    entity_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)
    previous_event_hash: str | None = None
    event_hash: str = ""
    schema_version: str = Field(default="1.0", max_length=10)

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 digest of this audit event."""
        canonical_payload = canonicalize_payload(self.payload)
        norm_ts = normalize_timestamp_str(self.timestamp)
        prev_hash = self.previous_event_hash or "GENESIS"

        hash_input = (
            f"v={self.schema_version}|"
            f"seq={self.sequence_number}|"
            f"id={self.id}|"
            f"case={self.case_id}|"
            f"actor={self.actor_id or ''}|"
            f"type={self.event_type.value}|"
            f"entity={self.entity_type.value}:{self.entity_id}|"
            f"time={norm_ts}|"
            f"prev={prev_hash}|"
            f"payload={canonical_payload}"
        )
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    def seal(self, previous_hash: str | None = None) -> "AuditEvent":
        """Set previous_event_hash and compute event_hash."""
        self.previous_event_hash = previous_hash
        self.event_hash = self.compute_hash()
        return self

    def is_valid(self) -> bool:
        """Verify that event_hash matches the computed hash."""
        return bool(self.event_hash and self.event_hash == self.compute_hash())


class AuditCheckpoint(BaseModel):
    """Independently recorded checkpoint representing verified head of an audit chain."""

    case_id: str
    head_event_id: str
    head_event_hash: str
    event_count: int
    updated_at: datetime = Field(default_factory=utc_now)
