"""Case domain use cases and lifecycle orchestration."""

from typing import Any

from document_intelligence.core.exceptions import EntityNotFoundException
from document_intelligence.domain.enums import AuditEventType, CaseStatus, EntityType
from document_intelligence.domain.models.case import Case
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.modules.audit.ledger import AuditLedgerService


class CaseService:
    """Application service orchestrating Case operations."""

    def __init__(self, case_repo: CaseRepository, audit_service: AuditLedgerService) -> None:
        self.case_repo = case_repo
        self.audit_service = audit_service

    def create_case(
        self,
        title: str,
        description: str | None = None,
        created_by: str | None = None,
        metadata: dict[str, Any] | None = None,
        organization_id: str | None = None,
    ) -> Case:
        """Create and persist a new investigation workspace."""
        case = Case(
            title=title,
            description=description,
            created_by=created_by,
            metadata=metadata or {},
            organization_id=organization_id,
        )
        saved_case = self.case_repo.save(case)

        # Audit event
        self.audit_service.record_event(
            case_id=saved_case.id,
            event_type=AuditEventType.CASE_CREATED,
            entity_type=EntityType.CASE,
            entity_id=saved_case.id,
            payload={
                "case_reference": saved_case.case_reference,
                "title": saved_case.title,
                "status": saved_case.status.value,
            },
            actor_id=created_by,
        )

        return saved_case

    def get_case(self, case_id: str) -> Case:
        """Fetch case by ID, raising EntityNotFoundException if missing."""
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException("Case", case_id)
        return case

    def list_cases(
        self,
        skip: int = 0,
        limit: int = 50,
        status: CaseStatus | None = None,
        accessible_case_ids: list[str] | None = None,
    ) -> tuple[list[Case], int]:
        """List cases with pagination and optional filter."""
        return self.case_repo.list_cases(
            skip=skip, limit=limit, status=status, accessible_case_ids=accessible_case_ids
        )

    def transition_status(
        self,
        case_id: str,
        target_status: CaseStatus,
        actor_id: str | None = None,
    ) -> Case:
        """Transition case to a new lifecycle state."""
        case = self.get_case(case_id)
        old_status = case.status

        case.transition_to(target_status)
        saved_case = self.case_repo.save(case)

        self.audit_service.record_event(
            case_id=saved_case.id,
            event_type=AuditEventType.CASE_STATUS_CHANGED,
            entity_type=EntityType.CASE,
            entity_id=saved_case.id,
            payload={
                "previous_status": old_status.value,
                "new_status": target_status.value,
            },
            actor_id=actor_id,
        )

        return saved_case

    def archive_case(self, case_id: str, actor_id: str | None = None) -> Case:
        """Safely archive case, preserving all forensic history, evidence, and audit trails."""
        return self.transition_status(case_id, CaseStatus.ARCHIVED, actor_id=actor_id)
