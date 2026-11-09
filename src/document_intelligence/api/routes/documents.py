"""Document upload and registry endpoints."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel

from document_intelligence.api.dependencies import get_document_service
from document_intelligence.domain.models.document import Document
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
    document_service: DocumentService = Depends(get_document_service),
) -> Document:
    """Safely upload and register an original document into an investigation case."""
    declared_name = file.filename or "unnamed_document"
    media_type = file.content_type or "application/octet-stream"

    return document_service.ingest_document(
        case_id=case_id,
        file_obj=file.file,
        declared_filename=declared_name,
        declared_media_type=media_type,
        created_by=created_by,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    case_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    """List all documents registered in a case."""
    items, total = document_service.list_documents(case_id=case_id, skip=skip, limit=limit)
    return DocumentListResponse(items=items, total=total, skip=skip, limit=limit)
