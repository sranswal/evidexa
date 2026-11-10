"""Forensic analysis execution, processing run, and evidence query endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import (
    get_analyzer_registry,
    get_case_service,
    get_evidence_repository,
    get_forensic_processing_service,
    get_processing_run_repository,
    require_case_access,
)
from document_intelligence.core.exceptions import NotFoundException
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.domain.models.processing_run import ProcessingRun
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.forensics.application.processing_service import (
    ForensicProcessingService,
)
from document_intelligence.modules.forensics.interfaces.registry import AnalyzerRegistry

router = APIRouter(prefix="/cases/{case_id}", tags=["Forensics"])


class AnalyzerInfo(BaseModel):
    """Metadata describing an available forensic analyzer engine."""

    analyzer_id: str
    display_name: str
    version: str


class AnalyzeDocumentRequest(BaseModel):
    """Request payload to initiate forensic analysis on a document."""

    analyzer_id: str = Field(
        default="pdf-structural-analyzer",
        description="Identifier of registered forensic analyzer to execute.",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional engine configuration parameters.",
    )


class AnalyzeDocumentResponse(BaseModel):
    """Response containing the completed processing run and detected findings."""

    processing_run: ProcessingRun
    findings: list[ForensicFinding]


class ProcessingRunListResponse(BaseModel):
    """Paginated collection of processing runs."""

    items: list[ProcessingRun]
    total: int
    skip: int
    limit: int


class EvidenceListResponse(BaseModel):
    """Paginated collection of evidence nodes."""

    items: list[EvidenceNode]
    total: int
    skip: int
    limit: int


@router.get("/analyzers", response_model=list[AnalyzerInfo])
async def list_analyzers(
    case_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
    registry: AnalyzerRegistry = Depends(get_analyzer_registry),
) -> list[AnalyzerInfo]:
    """Retrieve list of registered forensic analysis engines."""
    case_service.get_case(case_id)
    return [
        AnalyzerInfo(
            analyzer_id=a.analyzer_id,
            display_name=a.display_name,
            version=a.version,
        )
        for a in registry.list_analyzers()
    ]


@router.post(
    "/documents/{document_id}/analyze",
    response_model=AnalyzeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_document(
    case_id: str,
    document_id: str,
    request: AnalyzeDocumentRequest | None = None,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.INVESTIGATOR, is_mutation=True)),
    service: ForensicProcessingService = Depends(get_forensic_processing_service),
) -> AnalyzeDocumentResponse:
    """Execute forensic analysis on a stored document.

    Enforces pre- and post-analysis cryptographic integrity checks.
    Records provenance audit trail in the immutable ledger.
    """
    req = request or AnalyzeDocumentRequest()
    run, findings = service.analyze_document(
        case_id=case_id,
        document_id=document_id,
        analyzer_id=req.analyzer_id,
        options=req.options,
    )
    return AnalyzeDocumentResponse(processing_run=run, findings=findings)


@router.get("/processing-runs", response_model=ProcessingRunListResponse)
async def list_processing_runs(
    case_id: str,
    document_id: str | None = Query(default=None, description="Filter by document ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
    run_repo: ProcessingRunRepository = Depends(get_processing_run_repository),
) -> ProcessingRunListResponse:
    """Retrieve processing runs for a case."""
    case_service.get_case(case_id)
    items, total = run_repo.list_by_case(
        case_id=case_id,
        document_id=document_id,
        skip=skip,
        limit=limit,
    )
    return ProcessingRunListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/processing-runs/{run_id}", response_model=ProcessingRun)
async def get_processing_run(
    case_id: str,
    run_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
    run_repo: ProcessingRunRepository = Depends(get_processing_run_repository),
) -> ProcessingRun:
    """Retrieve a single processing run by ID."""
    case_service.get_case(case_id)
    run = run_repo.get_by_id(run_id)
    if not run or run.case_id != case_id:
        raise NotFoundException(
            f"Processing run '{run_id}' not found.",
            details={"run_id": run_id, "case_id": case_id},
        )
    return run


@router.get("/evidence", response_model=EvidenceListResponse)
async def list_evidence(
    case_id: str,
    document_id: str | None = Query(default=None, description="Filter by document ID"),
    processing_run_id: str | None = Query(default=None, description="Filter by processing run ID"),
    evidence_type: str | None = Query(default=None, description="Filter by evidence type"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
    evidence_repo: EvidenceRepository = Depends(get_evidence_repository),
) -> EvidenceListResponse:
    """Retrieve evidence nodes for a case with optional filters."""
    case_service.get_case(case_id)
    items, total = evidence_repo.list_by_case(
        case_id=case_id,
        document_id=document_id,
        processing_run_id=processing_run_id,
        evidence_type=evidence_type,
        skip=skip,
        limit=limit,
    )
    return EvidenceListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/evidence/{evidence_id}", response_model=EvidenceNode)
async def get_evidence(
    case_id: str,
    evidence_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    case_service: CaseService = Depends(get_case_service),
    evidence_repo: EvidenceRepository = Depends(get_evidence_repository),
) -> EvidenceNode:
    """Retrieve a single evidence node by ID."""
    case_service.get_case(case_id)
    evidence = evidence_repo.get_by_id(evidence_id)
    if not evidence or evidence.case_id != case_id:
        raise NotFoundException(
            f"Evidence node '{evidence_id}' not found.",
            details={"evidence_id": evidence_id, "case_id": case_id},
        )
    return evidence
