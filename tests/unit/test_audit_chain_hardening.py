"""Unit tests for hardened audit ledger: tail deletion detection, sequence continuity, and concurrency."""

from concurrent.futures import ThreadPoolExecutor

from document_intelligence.domain.enums import AuditEventType, EntityType
from document_intelligence.domain.identifiers import utc_now
from document_intelligence.infrastructure.persistence.models import AuditEventModel, CaseModel
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


class TestAuditChainHardening:
    """Test head checkpointing, tail truncation detection, sequence verification, and concurrency."""

    def test_tail_event_deletion_detected_by_checkpoint(self, db_session) -> None:
        case_id = "case-tail-truncation"
        _create_case(db_session, case_id)

        repo = AuditRepository(db_session)
        service = AuditLedgerService(repo)

        # Record 4 events
        for i in range(1, 5):
            service.record_event(
                case_id=case_id,
                event_type=AuditEventType.DOCUMENT_INGESTED,
                entity_type=EntityType.DOCUMENT,
                entity_id=f"doc-{i}",
                payload={"step": i},
            )

        # Before tampering: chain is valid
        is_valid, error = service.verify_chain(case_id)
        assert is_valid is True
        assert error is None

        # Delete the final (4th) event directly from database
        latest_event = (
            db_session.query(AuditEventModel)
            .filter_by(case_id=case_id)
            .order_by(AuditEventModel.sequence_number.desc())
            .first()
        )
        assert latest_event is not None
        assert latest_event.sequence_number == 4
        db_session.delete(latest_event)
        db_session.commit()

        # Without checkpointing, the remaining 3 events form a mathematically valid chain!
        # But with head checkpointing, tail deletion MUST be detected:
        is_valid, error = service.verify_chain(case_id)
        assert is_valid is False
        assert "Tail truncation detected" in str(error)

    def test_sequence_number_gap_detected(self, db_session) -> None:
        case_id = "case-seq-gap"
        _create_case(db_session, case_id)

        repo = AuditRepository(db_session)
        service = AuditLedgerService(repo)

        service.record_event(
            case_id=case_id,
            event_type=AuditEventType.CASE_CREATED,
            entity_type=EntityType.CASE,
            entity_id=case_id,
            payload={"name": "event 1"},
        )
        service.record_event(
            case_id=case_id,
            event_type=AuditEventType.DOCUMENT_INGESTED,
            entity_type=EntityType.DOCUMENT,
            entity_id="doc-1",
            payload={"name": "event 2"},
        )

        # Alter second event sequence number to introduce a gap (e.g. 3 instead of 2)
        ev2 = (
            db_session.query(AuditEventModel).filter_by(case_id=case_id, sequence_number=2).first()
        )
        assert ev2 is not None
        ev2.sequence_number = 3
        db_session.commit()

        is_valid, error = service.verify_chain(case_id)
        assert is_valid is False
        assert "Sequence discontinuity" in str(error)

    def test_concurrent_event_writes_serialize_safely(self, test_settings) -> None:
        """Verify that concurrent writes to the same case serialize without sequence collision."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from document_intelligence.infrastructure.persistence.database import Base

        engine = create_engine(
            test_settings.database_url, connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        case_id = "case-concurrency-test"
        with Session() as s:
            _create_case(s, case_id)

        num_threads = 8
        num_events_per_thread = 5
        total_events = num_threads * num_events_per_thread

        def record_worker(thread_idx: int) -> None:
            with Session() as session:
                repo = AuditRepository(session)
                service = AuditLedgerService(repo)
                for step in range(num_events_per_thread):
                    service.record_event(
                        case_id=case_id,
                        event_type=AuditEventType.DOCUMENT_INGESTED,
                        entity_type=EntityType.DOCUMENT,
                        entity_id=f"doc-{thread_idx}-{step}",
                        payload={"thread": thread_idx, "step": step},
                    )

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(record_worker, i) for i in range(num_threads)]
            for f in futures:
                f.result()

        with Session() as session:
            repo = AuditRepository(session)
            service = AuditLedgerService(repo)
            events, total = service.list_events(case_id, limit=100)
            assert total == total_events
            assert len(events) == total_events

            # Verify sequence numbers are strictly 1..total_events
            sequences = [e.sequence_number for e in events]
            assert sequences == list(range(1, total_events + 1))

            # Verify entire chain is cryptographically intact
            is_valid, error = service.verify_chain(case_id)
            assert is_valid is True
            assert error is None
