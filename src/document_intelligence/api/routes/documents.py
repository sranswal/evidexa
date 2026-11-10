"""Document upload and registry endpoints."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from document_intelligence.api.dependencies import (
    get_current_user,
    get_document_service,
    get_storage,
    require_case_access,
)
from document_intelligence.core.exceptions import EntityNotFoundException
from document_intelligence.core.security import sanitize_filename
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.document import Document
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.documents.service import DocumentService

router = APIRouter(prefix="/cases/{case_id}/documents", tags=["Documents"])


class DocumentListResponse(BaseModel):
    items: list[Document]
    total: int
    skip: int
    limit: int


@router.post("", response_model=Document, status_code=status.HTTP_201_CREATED)
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    created_by: str | None = Form(default=None),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.INVESTIGATOR, is_mutation=True)),
    current_user: UserModel = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> Document:
    """Safely upload and register an original document into an investigation case.

    Attribution is strictly bound to the authenticated principal.
    """
    declared_name = file.filename or "unnamed_document"
    media_type = file.content_type or "application/octet-stream"

    return document_service.ingest_document(
        case_id=case_id,
        file_obj=file.file,
        declared_filename=declared_name,
        declared_media_type=media_type,
        created_by=current_user.id,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    case_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    """List all documents registered in a case."""
    items, total = document_service.list_documents(case_id=case_id, skip=skip, limit=limit)
    return DocumentListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{document_id}", response_model=Document)
async def get_document(
    case_id: str,
    document_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    document_service: DocumentService = Depends(get_document_service),
) -> Document:
    """Retrieve detailed metadata for a registered document within a case."""
    return document_service.get_document(case_id=case_id, document_id=document_id)


@router.get("/{document_id}/download")
async def download_document(
    case_id: str,
    document_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    document_service: DocumentService = Depends(get_document_service),
    storage: DocumentStorageProtocol = Depends(get_storage),
) -> FileResponse:
    """Download or stream the original verified evidence document."""
    doc = document_service.get_document(case_id=case_id, document_id=document_id)
    path = storage.get_original_path(doc.storage_key)
    if not path.exists():
        raise EntityNotFoundException("DocumentFile", document_id)
    return FileResponse(
        path=path,
        media_type=doc.media_type,
        filename=doc.original_filename,
    )


@router.get("/{document_id}/artifacts/{run_id}/{filename:path}")
async def get_document_artifact(
    case_id: str,
    document_id: str,
    run_id: str,
    filename: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    document_service: DocumentService = Depends(get_document_service),
    storage: DocumentStorageProtocol = Depends(get_storage),
) -> FileResponse:
    """Retrieve a forensic artifact generated for a document during a processing run."""
    document_service.get_document(case_id=case_id, document_id=document_id)
    clean_name = sanitize_filename(filename)
    artifact_key = f"{case_id}/{document_id}/{run_id}/{clean_name}"
    try:
        path = storage.get_artifact_path(artifact_key)
        if not path.exists():
            raise EntityNotFoundException("ArtifactFile", filename)
    except Exception as exc:
        if isinstance(exc, EntityNotFoundException):
            raise
        raise EntityNotFoundException("ArtifactFile", filename) from exc

    if clean_name.lower().endswith(".png"):
        media_type = "image/png"
    elif clean_name.lower().endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif clean_name.lower().endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=clean_name,
    )
