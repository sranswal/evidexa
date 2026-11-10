"""Dossier and aggregated findings API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_current_user,
    get_dossier_service,
    require_case_access,
)
from document_intelligence.domain.enums import DossierFormat, InvestigatorReviewAction
from document_intelligence.domain.models.aggregated_finding import (
    AggregatedFinding,
    AggregatedFindingReview,
)
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.investigation_dossier import InvestigationDossier
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.modules.dossier.service import InvestigationDossierService

router = APIRouter(prefix="/cases/{case_id}", tags=["Investigation Dossier & Findings"])


class ReviewCreateRequest(BaseModel):
    """Request payload for recording an investigator review on an aggregated finding."""

    reviewer_id: str | None = Field(default=None, max_length=100)
    action: InvestigatorReviewAction
    rationale: str = Field(min_length=1, max_length=4000)


class DossierGenerateRequest(BaseModel):
    """Request payload for generating an investigation evidence dossier."""

    created_by: str | None = Field(default=None, max_length=100)
    scope_and_purpose: str | None = Field(default=None, max_length=2000)


class DossierFinalizeRequest(BaseModel):
    """Request payload for finalizing and sealing an investigation evidence dossier."""

    user_id: str | None = Field(default=None, max_length=100)


@router.get(
    "/findings/aggregated",
    response_model=list[AggregatedFinding],
    summary="Get aggregated case findings",
)
def get_aggregated_findings(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: InvestigationDossierService = Depends(get_dossier_service),
) -> list[AggregatedFinding]:
    """Compile and retrieve unified findings across all forensic and consistency subsystems."""
    return service.get_aggregated_findings(case_id)


@router.post(
    "/findings/aggregated/{finding_id}/reviews",
    response_model=AggregatedFindingReview,
    status_code=status.HTTP_201_CREATED,
    summary="Record investigator review on an aggregated finding",
)
def record_finding_review(
    case_id: str,
    finding_id: str,
    request: ReviewCreateRequest,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.REVIEWER, is_mutation=True)),
    current_user: UserModel = Depends(get_current_user),
    service: InvestigationDossierService = Depends(get_dossier_service),
) -> AggregatedFindingReview:
    """Record an append-only investigator review assertion on an aggregated finding."""
    actor_id = (
        request.reviewer_id
        if (current_user.id == "usr-system-admin-001" and request.reviewer_id)
        else current_user.id
    )
    return service.record_finding_review(
        case_id=case_id,
        finding_id=finding_id,
        reviewer_id=actor_id,
        action=request.action,
        rationale=request.rationale,
    )


@router.get(
    "/findings/aggregated/{finding_id}/reviews",
    response_model=list[AggregatedFindingReview],
    summary="List review history for an aggregated finding",
)
def list_finding_reviews(
    case_id: str,
    finding_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: InvestigationDossierService = Depends(get_dossier_service),
) -> list[AggregatedFindingReview]:
    """Retrieve chronological investigator reviews recorded for an aggregated finding."""
    return service.list_finding_reviews(case_id, finding_id)


@router.post(
    "/dossiers/generate",
    response_model=InvestigationDossier,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a comprehensive investigation dossier draft",
)
def generate_dossier(
    case_id: str,
    request: DossierGenerateRequest,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.INVESTIGATOR, is_mutation=True)),
    current_user: UserModel = Depends(get_current_user),
    service: InvestigationDossierService = Depends(get_dossier_service),
) -> InvestigationDossier:
    """Compile and generate an investigation dossier structured across 12 analytical sections."""
    creator_id = (
        request.created_by
        if (current_user.id == "usr-system-admin-001" and request.created_by)
        else current_user.id
    )
    return service.generate_dossier(
        case_id=case_id,
        created_by=creator_id,
        scope_and_purpose=request.scope_and_purpose,
    )


@router.get(
    "/dossiers",
    response_model=list[InvestigationDossier],
    summary="List investigation dossiers for a case",
)
def list_dossiers(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: InvestigationDossierService = Depends(get_dossier_service),
) -> list[InvestigationDossier]:
    """Retrieve all dossiers associated with a case."""
    return service.list_dossiers(case_id)


@router.get(
    "/dossiers/{dossier_id}",
    response_model=InvestigationDossier,
    summary="Get a specific investigation dossier",
)
def get_dossier(
    case_id: str,
    dossier_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: InvestigationDossierService = Depends(get_dossier_service),
) -> InvestigationDossier:
    """Retrieve detailed dossier representation including all 12 sections and hash."""
    return service.get_dossier(case_id, dossier_id)


@router.post(
    "/dossiers/{dossier_id}/finalize",
    response_model=InvestigationDossier,
    summary="Finalize and seal an investigation dossier",
)
def finalize_dossier(
    case_id: str,
    dossier_id: str,
    request: DossierFinalizeRequest,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.REVIEWER, is_mutation=True)),
    current_user: UserModel = Depends(get_current_user),
    service: InvestigationDossierService = Depends(get_dossier_service),
) -> InvestigationDossier:
    """Freeze dossier content, compute canonical SHA-256 integrity hash, and transition to APPROVED."""
    actor_id = (
        request.user_id
        if (current_user.id == "usr-system-admin-001" and request.user_id)
        else current_user.id
    )
    return service.finalize_dossier(
        case_id=case_id,
        dossier_id=dossier_id,
        user_id=actor_id,
    )


@router.get(
    "/dossiers/{dossier_id}/export",
    summary="Export dossier as PDF or JSON artifact",
)
def export_dossier(
    case_id: str,
    dossier_id: str,
    format: str = Query(default="pdf", description="Export format (pdf or json)"),
    user_id: str = Query(default="investigator", description="User ID requesting export"),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: InvestigationDossierService = Depends(get_dossier_service),
) -> Response:
    """Render and export dossier into PDF or structured JSON with evidentiary disclaimers."""
    fmt_upper = format.strip().upper()
    try:
        export_fmt = DossierFormat(fmt_upper)
    except ValueError:
        export_fmt = DossierFormat.PDF

    content_bytes, media_type, filename = service.export_dossier(
        case_id=case_id,
        dossier_id=dossier_id,
        export_format=export_fmt,
        user_id=user_id,
    )
    return Response(
        content=content_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
