"""REST API endpoints for Optical Character Recognition (OCR) and Document Understanding."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_analyzer_registry,
    get_case_service,
    get_document_repository,
    get_forensic_processing_service,
    get_processing_run_repository,
    get_storage,
)
from document_intelligence.core.exceptions import NotFoundException
from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.domain.models.ocr import (
    ExtractedDocumentText,
    ExtractedTable,
    LayoutRegion,
    TextToken,
)
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.forensics.application.processing_service import (
    ForensicProcessingService,
)
from document_intelligence.modules.forensics.interfaces.registry import AnalyzerRegistry

router = APIRouter(
    prefix="/cases/{case_id}/documents/{document_id}/ocr",
    tags=["OCR & Document Understanding"],
)


class StartOcrRequest(BaseModel):
    """Request payload to initiate OCR and Document Understanding."""

    analyzer_id: str = Field(
        default="hybrid-ocr-pipeline",
        description="OCR engine identifier ('hybrid-ocr-pipeline', 'rapidocr-optical-engine', 'pdfium-ocr-engine').",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional configuration parameters (DPI, language, max_pages, force_ocr, sparse_threshold).",
    )


class StartOcrResponse(BaseModel):
    """Response containing processing run metadata and text summary."""

    processing_run: ProcessingRun
    summary: dict[str, Any]


class PaginatedTokensResponse(BaseModel):
    """Paginated list of extracted tokens with bounding boxes."""

    total_count: int
    offset: int
    limit: int
    tokens: list[TextToken]


def _get_latest_ocr_doc(
    case_id: str,
    document_id: str,
    case_service: CaseService,
    doc_repo: DocumentRepository,
    run_repo: ProcessingRunRepository,
    storage: DocumentStorageProtocol,
) -> ExtractedDocumentText:
    """Helper to locate and deserialize the latest OCR JSON artifact for a document."""
    case = case_service.get_case(case_id)
    doc = doc_repo.get_by_id(document_id)
    if not doc or doc.case_id != case.id:
        raise NotFoundException(
            f"Document '{document_id}' not found in case '{case_id}'.",
            details={"case_id": case_id, "document_id": document_id},
        )

    runs, _ = run_repo.list_by_case(case_id=case_id, document_id=document_id)
    ocr_runs = [
        r
        for r in runs
        if r.status in (PipelineStatus.SUCCEEDED, PipelineStatus.PARTIALLY_SUCCEEDED)
        and "ocr" in r.pipeline_name.lower()
    ]
    if not ocr_runs:
        raise NotFoundException(
            f"No completed OCR runs found for document '{document_id}'.",
            details={"case_id": case_id, "document_id": document_id},
        )

    # Pick the most recent completed run
    latest_run = sorted(ocr_runs, key=lambda r: r.started_at, reverse=True)[0]
    filename = f"ocr_{latest_run.id}_extracted.json"
    artifact_key = f"{case_id}/{document_id}/{latest_run.id}/{filename}"

    try:
        art_path = storage.get_artifact_path(artifact_key)
        if not art_path.exists():
            raise NotFoundException(f"OCR artifact not found at storage key '{artifact_key}'.")
        data = json.loads(art_path.read_text(encoding="utf-8"))
        return ExtractedDocumentText.model_validate(data)
    except Exception as e:
        raise NotFoundException(
            f"Could not load OCR extraction result: {e}",
            details={"artifact_key": artifact_key},
        ) from e


@router.post("", response_model=StartOcrResponse, status_code=status.HTTP_201_CREATED)
def start_ocr_analysis(
    case_id: str,
    document_id: str,
    payload: StartOcrRequest = StartOcrRequest(),
    processing_service: ForensicProcessingService = Depends(get_forensic_processing_service),
) -> StartOcrResponse:
    """Execute OCR and Document Understanding on a document within an active case."""
    run, findings = processing_service.analyze_document(
        case_id=case_id,
        document_id=document_id,
        analyzer_id=payload.analyzer_id,
        options=payload.options,
    )

    duration_ms = None
    if run.completed_at and run.started_at:
        duration_ms = round((run.completed_at - run.started_at).total_seconds() * 1000.0, 2)

    summary = {
        "pipeline_name": run.pipeline_name,
        "status": run.status.value,
        "execution_duration_ms": duration_ms,
        "findings_count": len(findings),
    }

    return StartOcrResponse(processing_run=run, summary=summary)


@router.get("/text", response_model=ExtractedDocumentText)
def get_extracted_text(
    case_id: str,
    document_id: str,
    page_number: int | None = Query(default=None, ge=1, description="Optional page number filter"),
    engine_name: str | None = Query(default=None, description="Filter pages by extraction engine"),
    extraction_status: str | None = Query(
        default=None, description="Filter pages by extraction status"
    ),
    language: str | None = Query(default=None, description="Filter by configured language"),
    case_service: CaseService = Depends(get_case_service),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    run_repo: ProcessingRunRepository = Depends(get_processing_run_repository),
    storage: DocumentStorageProtocol = Depends(get_storage),
) -> ExtractedDocumentText:
    """Retrieve full or filtered extracted text, tokens, and metadata."""
    doc_text = _get_latest_ocr_doc(case_id, document_id, case_service, doc_repo, run_repo, storage)

    if language is not None and doc_text.engine_metadata.language.lower() != language.lower():
        raise NotFoundException(
            f"No extraction found with language '{language}'. Document was extracted in '{doc_text.engine_metadata.language}'.",
            details={"configured_language": doc_text.engine_metadata.language},
        )

    filtered_pages = doc_text.pages
    if page_number is not None:
        filtered_pages = [p for p in filtered_pages if p.page_number == page_number]
        if not filtered_pages:
            raise NotFoundException(f"Page {page_number} not found in extracted document.")

    if engine_name is not None:
        e_lower = engine_name.lower()
        filtered_pages = [
            p for p in filtered_pages if p.engine_name and e_lower in p.engine_name.lower()
        ]

    if extraction_status is not None:
        s_lower = extraction_status.lower()
        filtered_pages = [p for p in filtered_pages if p.extraction_status.lower() == s_lower]

    return ExtractedDocumentText(
        document_id=doc_text.document_id,
        processing_run_id=doc_text.processing_run_id,
        engine_metadata=doc_text.engine_metadata,
        pages=filtered_pages,
        total_pages=len(filtered_pages),
        total_tokens=sum(len(p.tokens) for p in filtered_pages),
        full_raw_text="\n\n".join(p.raw_text for p in filtered_pages if p.raw_text),
        full_normalized_text="\n\n".join(
            p.normalized_text for p in filtered_pages if p.normalized_text
        ),
    )

    if extraction_status is not None:
        s_lower = extraction_status.lower()
        filtered_pages = [p for p in filtered_pages if p.extraction_status.lower() == s_lower]

    return ExtractedDocumentText(
        document_id=doc_text.document_id,
        processing_run_id=doc_text.processing_run_id,
        engine_metadata=doc_text.engine_metadata,
        pages=filtered_pages,
        total_pages=len(filtered_pages),
        total_tokens=sum(len(p.tokens) for p in filtered_pages),
        full_raw_text="\n\n".join(p.raw_text for p in filtered_pages if p.raw_text),
        full_normalized_text="\n\n".join(
            p.normalized_text for p in filtered_pages if p.normalized_text
        ),
    )


@router.get("/layout", response_model=list[LayoutRegion])
def get_extracted_layout(
    case_id: str,
    document_id: str,
    page_number: int | None = Query(default=None, ge=1),
    case_service: CaseService = Depends(get_case_service),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    run_repo: ProcessingRunRepository = Depends(get_processing_run_repository),
    storage: DocumentStorageProtocol = Depends(get_storage),
) -> list[LayoutRegion]:
    """Retrieve semantic layout regions (Headers, Footers, Paragraphs, Tables)."""
    doc_text = _get_latest_ocr_doc(case_id, document_id, case_service, doc_repo, run_repo, storage)
    regions: list[LayoutRegion] = []
    for page in doc_text.pages:
        if page_number is None or page.page_number == page_number:
            regions.extend(page.layout_regions)
    return regions


@router.get("/tables", response_model=list[ExtractedTable])
def get_extracted_tables(
    case_id: str,
    document_id: str,
    page_number: int | None = Query(default=None, ge=1),
    case_service: CaseService = Depends(get_case_service),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    run_repo: ProcessingRunRepository = Depends(get_processing_run_repository),
    storage: DocumentStorageProtocol = Depends(get_storage),
) -> list[ExtractedTable]:
    """Retrieve structured tables and cell grids extracted from the document."""
    doc_text = _get_latest_ocr_doc(case_id, document_id, case_service, doc_repo, run_repo, storage)
    tables: list[ExtractedTable] = []
    for page in doc_text.pages:
        if page_number is None or page.page_number == page_number:
            tables.extend(page.tables)
    return tables


@router.get("/tokens", response_model=PaginatedTokensResponse)
def get_extracted_tokens(
    case_id: str,
    document_id: str,
    page_number: int | None = Query(default=None, ge=1),
    engine_name: str | None = Query(default=None, description="Filter tokens by engine name"),
    query: str | None = Query(default=None, description="Optional text filter query"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    case_service: CaseService = Depends(get_case_service),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    run_repo: ProcessingRunRepository = Depends(get_processing_run_repository),
    storage: DocumentStorageProtocol = Depends(get_storage),
) -> PaginatedTokensResponse:
    """Retrieve token-level information with bounding boxes, search filtering, and pagination."""
    doc_text = _get_latest_ocr_doc(case_id, document_id, case_service, doc_repo, run_repo, storage)
    all_tokens: list[TextToken] = []
    for page in doc_text.pages:
        if page_number is not None and page.page_number != page_number:
            continue
        if engine_name is not None:
            if not page.engine_name or engine_name.lower() not in page.engine_name.lower():
                continue
        all_tokens.extend(page.tokens)

    if query:
        q_lower = query.lower()
        all_tokens = [
            t
            for t in all_tokens
            if q_lower in t.raw_text.lower()
            or (t.normalized_text and q_lower in t.normalized_text.lower())
        ]

    total_count = len(all_tokens)
    paginated = all_tokens[offset : offset + limit]

    return PaginatedTokensResponse(
        total_count=total_count,
        offset=offset,
        limit=limit,
        tokens=paginated,
    )


@router.get("/capabilities")
def get_ocr_capabilities(
    registry: AnalyzerRegistry = Depends(get_analyzer_registry),
) -> dict[str, Any]:
    """Retrieve capabilities and supported media types of registered OCR engines."""
    ocr_analyzers = [a for a in registry.list_analyzers() if "ocr" in a.analyzer_id.lower()]
    return {
        "registered_ocr_engines": [
            {
                "analyzer_id": a.analyzer_id,
                "display_name": a.display_name,
                "version": a.version,
                "supported_media_types": sorted(a.supported_media_types),
                "supported_capabilities": a.supported_capabilities,
            }
            for a in ocr_analyzers
        ]
    }
