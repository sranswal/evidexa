"""Audit ledger query and cryptographic verification endpoints."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from document_intelligence.api.dependencies import (
    get_audit_service,
    get_case_service,
    require_case_access,
)
from document_intelligence.domain.models.audit_event import AuditEvent
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.cases.service import CaseService

router = APIRouter(prefix="/cases/{case_id}/audit-events", tags=["Audit Ledger"])


class AuditEventListResponse(BaseModel):
    items: list[AuditEvent]
    total: int
    skip: int
    limit: int


class AuditVerificationResponse(BaseModel):
    case_id: str
    chain_valid: bool
    total_events: int
    error_message: str | None = None


@router.get("", response_model=AuditEventListResponse)
async def list_audit_events(
    case_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
    audit_service: AuditLedgerService = Depends(get_audit_service),
) -> AuditEventListResponse:
    """Retrieve immutable chronological audit events for a case."""
    # Verify case exists
    case_service.get_case(case_id)

    items, total = audit_service.list_events(case_id=case_id, skip=skip, limit=limit)
    return AuditEventListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/verify", response_model=AuditVerificationResponse)
async def verify_audit_chain(
    case_id: str,
    access_role: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
    audit_service: AuditLedgerService = Depends(get_audit_service),
) -> AuditVerificationResponse:
    """Verify cryptographic hash chain integrity for the specified case."""
    # Verify case exists
    case_service.get_case(case_id)

    is_valid, error_msg = audit_service.verify_chain(case_id)
    _, total = audit_service.list_events(case_id=case_id, skip=0, limit=1)

    return AuditVerificationResponse(
        case_id=case_id,
        chain_valid=is_valid,
        total_events=total,
        error_message=error_msg,
    )
