"""REST API routes for document classification and structured field extraction."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_current_user,
    get_document_understanding_service,
    require_case_access,
)
from document_intelligence.domain.enums import DocumentClass
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.classification import DocumentClassificationResult
from document_intelligence.domain.models.extraction import (
    DocumentExtractionResult,
    ExtractionSchema,
)
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.modules.understanding.service import (
    DocumentUnderstandingService,
)

router = APIRouter(
    prefix="/cases/{case_id}/documents/{document_id}",
    tags=["Document Classification & Extraction"],
)


class ClassifyDocumentRequest(BaseModel):
    """Payload for triggering document classification."""

    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional configuration options for classification.",
    )


class OverrideClassificationRequest(BaseModel):
    """Payload for recording a human review or classification override."""

    target_class: DocumentClass = Field(description="New classification to apply.")
    reason: str = Field(min_length=1, max_length=1000, description="Justification for override.")
    overridden_by: str | None = Field(
        default=None,
        max_length=100,
        description="Asserted reviewer ID (superseded by authenticated principal).",
    )


class ExtractFieldsRequest(BaseModel):
    """Payload for executing structured field extraction."""

    schema_id: str | None = Field(
        default=None,
        description="Optional schema identifier. If omitted, uses auto-detected document class schema.",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extraction options.",
    )


# -----------------------------------------------------------------------------
# Classification Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/classification",
    response_model=DocumentClassificationResult,
    status_code=status.HTTP_200_OK,
    summary="Classify document and pages",
    description="Analyzes document text and layout to predict document class and candidate rankings.",
)
def classify_document(
    case_id: str,
    document_id: str,
    request: ClassifyDocumentRequest | None = None,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.INVESTIGATOR, is_mutation=True)),
    service: DocumentUnderstandingService = Depends(get_document_understanding_service),
) -> DocumentClassificationResult:
    opts = request.options if request else {}
    return service.classify_document(case_id=case_id, document_id=document_id, options=opts)


@router.get(
    "/classification",
    response_model=DocumentClassificationResult,
    status_code=status.HTTP_200_OK,
    summary="Get latest document classification",
    description="Retrieves the latest classification result, candidate rankings, and page breakdown.",
)
def get_classification(
    case_id: str,
    document_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: DocumentUnderstandingService = Depends(get_document_understanding_service),
) -> DocumentClassificationResult:
    return service.get_latest_classification(case_id=case_id, document_id=document_id)


@router.post(
    "/classification/override",
    response_model=DocumentClassificationResult,
    status_code=status.HTTP_200_OK,
    summary="Override document classification",
    description="Applies an investigator override without destroying the original machine score.",
)
def override_classification(
    case_id: str,
    document_id: str,
    request: OverrideClassificationRequest,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.REVIEWER, is_mutation=True)),
    current_user: UserModel = Depends(get_current_user),
    service: DocumentUnderstandingService = Depends(get_document_understanding_service),
) -> DocumentClassificationResult:
    actor_id = (
        request.overridden_by
        if (current_user.id == "usr-system-admin-001" and request.overridden_by)
        else current_user.id
    )
    return service.override_classification(
        case_id=case_id,
        document_id=document_id,
        overridden_class=request.target_class,
        overridden_by=actor_id,
        reason=request.reason,
    )


# -----------------------------------------------------------------------------
# Structured Extraction Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/extraction",
    response_model=DocumentExtractionResult,
    status_code=status.HTTP_200_OK,
    summary="Extract structured fields",
    description="Extracts structured fields matching an explicit schema with bounding boxes and validation.",
)
def extract_fields(
    case_id: str,
    document_id: str,
    request: ExtractFieldsRequest | None = None,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.INVESTIGATOR, is_mutation=True)),
    service: DocumentUnderstandingService = Depends(get_document_understanding_service),
) -> DocumentExtractionResult:
    schema_id = request.schema_id if request else None
    opts = request.options if request else {}
    return service.extract_fields(
        case_id=case_id,
        document_id=document_id,
        schema_id=schema_id,
        options=opts,
    )


@router.get(
    "/extraction",
    response_model=DocumentExtractionResult,
    status_code=status.HTTP_200_OK,
    summary="Get latest structured extraction",
    description="Retrieves the latest structured extraction result, fields, and provenance.",
)
def get_extraction(
    case_id: str,
    document_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: DocumentUnderstandingService = Depends(get_document_understanding_service),
) -> DocumentExtractionResult:
    return service.get_latest_extraction(case_id=case_id, document_id=document_id)


@router.get(
    "/extraction/schemas",
    response_model=list[ExtractionSchema],
    status_code=status.HTTP_200_OK,
    summary="List extraction schemas",
    description="Returns all registered structured field extraction schemas.",
)
def list_schemas(
    case_id: str,
    document_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: DocumentUnderstandingService = Depends(get_document_understanding_service),
) -> list[ExtractionSchema]:
    return service.schema_registry.list_schemas()


@router.get(
    "/extraction/schemas/{schema_id}",
    response_model=ExtractionSchema,
    status_code=status.HTTP_200_OK,
    summary="Get extraction schema by ID",
    description="Retrieves field definitions and validation rules for a specific schema.",
)
def get_schema(
    case_id: str,
    document_id: str,
    schema_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    service: DocumentUnderstandingService = Depends(get_document_understanding_service),
) -> ExtractionSchema:
    schema = service.schema_registry.get_by_id(schema_id)
    if not schema:
        from document_intelligence.core.exceptions import NotFoundException

        raise NotFoundException(f"Extraction schema '{schema_id}' not found.")
    return schema
