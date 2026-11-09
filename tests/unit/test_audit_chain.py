"""Unit tests for the immutable audit event ledger and cryptographic hash chaining."""

from document_intelligence.domain.enums import AuditEventType, EntityType
from document_intelligence.domain.identifiers import utc_now
from document_intelligence.domain.models.audit_event import AuditEvent, canonicalize_payload
from document_intelligence.infrastructure.persistence.models import CaseModel
from document_intelligence.infrastructure.repositories.audit_repository import AuditRepository
from document_intelligence.modules.audit.ledger import AuditLedgerService


def _create_case(db_session, case_id: str) -> None:
    case = CaseModel(
        id=case_id,
        case_reference=f"REF-{case_id}",
        title=f"Test Case {case_id}",
        status="ACTIVE",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db_session.add(case)
    db_session.commit()


class TestCanonicalPayload:
    """Test deterministic payload serialization."""

    def test_canonicalize_payload_key_order_invariance(self) -> None:
        p1 = {"b": 2, "a": 1, "nested": {"z": 10, "y": 20}}
        p2 = {"nested": {"y": 20, "z": 10}, "a": 1, "b": 2}
        assert canonicalize_payload(p1) == canonicalize_payload(p2)


class TestAuditLedgerHashChaining:
    """Test append, verification, tampering detection, and reordering detection."""

    def test_single_event_sealing_and_verification(self) -> None:
        event = AuditEvent(
            case_id="case-100",
            sequence_number=1,
            actor_id="admin",
            event_type=AuditEventType.CASE_CREATED,
            entity_type=EntityType.CASE,
            entity_id="case-100",
            payload={"title": "Test Investigation"},
        )
        assert event.event_hash == ""
        event.seal(previous_hash=None)
        assert len(event.event_hash) == 64
        assert event.is_valid() is True

    def test_audit_chain_verification_end_to_end(self, db_session) -> None:
        case_id = "case-chain-1"
        _create_case(db_session, case_id)

        repo = AuditRepository(db_session)
        service = AuditLedgerService(repo)

        # Record sequence of 3 events
        e1 = service.record_event(
            case_id=case_id,
            event_type=AuditEventType.CASE_CREATED,
            entity_type=EntityType.CASE,
            entity_id=case_id,
            payload={"title": "Case Created"},
        )
        assert e1.previous_event_hash is None
        assert e1.sequence_number == 1

        e2 = service.record_event(
            case_id=case_id,
            event_type=AuditEventType.DOCUMENT_INGESTED,
            entity_type=EntityType.DOCUMENT,
            entity_id="doc-1",
            payload={"filename": "invoice.pdf"},
        )
        assert e2.previous_event_hash == e1.event_hash
        assert e2.sequence_number == 2

        e3 = service.record_event(
            case_id=case_id,
            event_type=AuditEventType.FILE_HASH_REGISTERED,
            entity_type=EntityType.DOCUMENT,
            entity_id="doc-1",
            payload={"sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"},
        )
        assert e3.previous_event_hash == e2.event_hash
        assert e3.sequence_number == 3

        is_valid, error = service.verify_chain(case_id)
        assert is_valid is True
        assert error is None

    def test_tampering_detection(self, db_session) -> None:
        case_id = "case-tamper-test"
        _create_case(db_session, case_id)

        repo = AuditRepository(db_session)
        service = AuditLedgerService(repo)

        service.record_event(
            case_id=case_id,
            event_type=AuditEventType.CASE_CREATED,
            entity_type=EntityType.CASE,
            entity_id=case_id,
            payload={"initial": "data"},
        )
        service.record_event(
            case_id=case_id,
            event_type=AuditEventType.DOCUMENT_INGESTED,
            entity_type=EntityType.DOCUMENT,
            entity_id="doc-1",
            payload={"tamper": "target"},
        )

        # Directly tamper with the database row
        from document_intelligence.infrastructure.persistence.models import AuditEventModel

        tamper_target = db_session.query(AuditEventModel).filter_by(entity_id="doc-1").first()
        assert tamper_target is not None
        tamper_target.payload = {"tamper": "MALICIOUSLY_ALTERED"}
        db_session.commit()

        is_valid, error = service.verify_chain(case_id)
        assert is_valid is False
        assert "Event content has been modified" in str(error)

    def test_deleted_event_detection(self, db_session) -> None:
        case_id = "case-deletion-test"
        _create_case(db_session, case_id)

        repo = AuditRepository(db_session)
        service = AuditLedgerService(repo)

        service.record_event(
            case_id=case_id,
            event_type=AuditEventType.CASE_CREATED,
            entity_type=EntityType.CASE,
            entity_id=case_id,
            payload={"step": 1},
        )
        service.record_event(
            case_id=case_id,
            event_type=AuditEventType.DOCUMENT_INGESTED,
            entity_type=EntityType.DOCUMENT,
            entity_id="doc-1",
            payload={"step": 2},
        )
        service.record_event(
            case_id=case_id,
            event_type=AuditEventType.FILE_HASH_REGISTERED,
            entity_type=EntityType.DOCUMENT,
            entity_id="doc-1",
            payload={"step": 3},
        )

        # Delete the middle event
        from document_intelligence.infrastructure.persistence.models import AuditEventModel

        middle_event = (
            db_session.query(AuditEventModel).filter_by(event_type="DOCUMENT_INGESTED").first()
        )
        assert middle_event is not None
        db_session.delete(middle_event)
        db_session.commit()

        is_valid, error = service.verify_chain(case_id)
        assert is_valid is False
        assert "truncation" in str(error).lower() or "broken link" in str(error).lower()
