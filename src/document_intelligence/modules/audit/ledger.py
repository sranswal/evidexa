"""Audit ledger service implementing cryptographic hash chaining and chain verification."""

import threading
from collections import defaultdict
from typing import Any

from document_intelligence.domain.enums import AuditEventType, EntityType
from document_intelligence.domain.models.audit_event import AuditEvent
from document_intelligence.infrastructure.repositories.audit_repository import AuditRepository

# Case-level synchronization locks to serialize concurrent writes per case
_case_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_registry_lock = threading.Lock()


def _get_case_lock(case_id: str) -> threading.Lock:
    with _registry_lock:
        return _case_locks[case_id]


class AuditLedgerService:
    """Service managing append-only provenance records and cryptographic integrity verification."""

    def __init__(self, audit_repo: AuditRepository) -> None:
        self.audit_repo = audit_repo

    def record_event(
        self,
        case_id: str,
        event_type: AuditEventType,
        entity_type: EntityType,
        entity_id: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
    ) -> AuditEvent:
        """Append an auditable action to the case's hash chain with per-case concurrency safety."""
        with _get_case_lock(case_id):
            latest_event = self.audit_repo.get_latest_event(case_id)
            previous_hash = latest_event.event_hash if latest_event else None
            next_seq = (latest_event.sequence_number + 1) if latest_event else 1

            event = AuditEvent(
                case_id=case_id,
                sequence_number=next_seq,
                actor_id=actor_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
            )
            event.seal(previous_hash=previous_hash)

            return self.audit_repo.append(event)

    def list_events(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AuditEvent], int]:
        """List chronological events for a case."""
        return self.audit_repo.list_by_case(case_id, skip=skip, limit=limit)

    def verify_chain(self, case_id: str) -> tuple[bool, str | None]:
        """Verify complete cryptographic chain integrity for a case against head checkpoint.

        Checks:
        1. Checkpoint existence and event count match.
        2. Latest event hash matches trusted checkpoint head hash.
        3. Strict monotonic sequence numbers (1, 2, ..., N).
        4. Each event's computed hash matches its recorded event_hash.
        5. Each event's previous_event_hash matches the previous event's event_hash.

        Returns:
            Tuple of (is_valid, error_description)
        """
        checkpoint = self.audit_repo.get_checkpoint(case_id)
        events = self.audit_repo.get_all_for_chain_verification(case_id)

        if not events:
            if checkpoint and checkpoint.event_count > 0:
                return (
                    False,
                    f"Tamper detected: Head checkpoint expects {checkpoint.event_count} events, but chain is empty.",
                )
            return True, None

        # Checkpoint validation
        if not checkpoint:
            return False, "Missing head checkpoint for case audit ledger."

        if len(events) != checkpoint.event_count:
            return (
                False,
                f"Tail truncation detected: Checkpoint expects {checkpoint.event_count} events, but found {len(events)}.",
            )

        if events[-1].event_hash != checkpoint.head_event_hash:
            return (
                False,
                f"Head hash mismatch: Checkpoint expects '{checkpoint.head_event_hash}', but latest event has '{events[-1].event_hash}'.",
            )

        expected_prev_hash: str | None = None

        for idx, event in enumerate(events):
            expected_seq = idx + 1
            # Check sequence continuity
            if event.sequence_number != expected_seq:
                msg = (
                    f"Sequence discontinuity at index {idx} (Event ID: {event.id}). "
                    f"Expected sequence {expected_seq}, got {event.sequence_number}."
                )
                return False, msg

            # Check event payload tampering
            if not event.is_valid():
                msg = (
                    f"Hash mismatch at sequence {event.sequence_number} (Event ID: {event.id}). "
                    f"Event content has been modified."
                )
                return False, msg

            # Check linkage to previous block
            if event.previous_event_hash != expected_prev_hash:
                msg = (
                    f"Broken link at sequence {event.sequence_number} (Event ID: {event.id}). "
                    f"Expected previous hash '{expected_prev_hash}', got '{event.previous_event_hash}'."
                )
                return False, msg

            expected_prev_hash = event.event_hash

        return True, None
