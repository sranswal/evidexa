"""REST API routes for the Grounded AI Investigation Assistant."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status

from document_intelligence.api.dependencies import (
    get_assistant_service,
    require_case_access,
)
from document_intelligence.domain.models.assistant import (
    AssistantQueryRequest,
    AssistantQueryResponse,
)
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.modules.assistant.service import AssistantService

router = APIRouter(
    prefix="/cases/{case_id}/assistant",
    tags=["Grounded AI Assistant"],
)


@router.post(
    "/query",
    response_model=AssistantQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the grounded investigation assistant",
    description="Submits an investigator question and receives a bounded, evidence-grounded response with traceable citations.",
)
def query_assistant(
    case_id: str,
    request: AssistantQueryRequest,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantQueryResponse:
    """Execute a grounded case query, enforcing case boundaries and epistemic separation."""
    return service.query(case_id=case_id, request=request)


@router.get(
    "/context-summary",
    status_code=status.HTTP_200_OK,
    summary="Get evidence summary for assistant initialization",
    description="Retrieves a high-level summary of documents, findings, and entities available for assistant grounding in this case.",
)
def get_assistant_context_summary(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: AssistantService = Depends(get_assistant_service),
) -> dict[str, Any]:
    """Retrieve counts and available evidentiary sources for the active case."""
    return service.get_context_summary(case_id=case_id)
