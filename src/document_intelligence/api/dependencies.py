"""FastAPI dependency injection providers."""

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from document_intelligence.core.config import Settings, settings
from document_intelligence.core.exceptions import AuthenticationException
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.infrastructure.persistence.database import get_db
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.infrastructure.repositories.audit_repository import AuditRepository
from document_intelligence.infrastructure.repositories.auth_repository import AuthRepository
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.consistency_repository import (
    ConsistencyRepository,
)
from document_intelligence.infrastructure.repositories.cross_case_repository import (
    CrossCaseRepository,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.dossier_repository import (
    DossierRepository,
)
from document_intelligence.infrastructure.repositories.entity_match_repository import (
    EntityMatchRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.finding_repository import (
    FindingRepository,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.repositories.relationship_repository import (
    RelationshipRepository,
)
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.assistant.provider import get_llm_provider
from document_intelligence.modules.assistant.retriever import CaseEvidenceRetriever
from document_intelligence.modules.assistant.service import AssistantService
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.auth.service import AuthenticationService, CaseAccessService
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.consistency.service import ConsistencyAnalysisService
from document_intelligence.modules.cross_case.service import CrossCaseCorrelationService
from document_intelligence.modules.documents.service import DocumentService
from document_intelligence.modules.dossier.service import InvestigationDossierService
from document_intelligence.modules.entity_resolution.service import (
    EntityResolutionService,
)
from document_intelligence.modules.forensics.adapters.ocr import (
    DevanagariRapidOcrAdapter,
    HybridOcrAdapter,
    PdfiumOcrAdapter,
    RapidOcrAdapter,
)
from document_intelligence.modules.forensics.adapters.pdf_structural.adapter import (
    PdfStructuralAnalyzer,
)
from document_intelligence.modules.forensics.adapters.visual import (
    CopyMoveAnalyzer,
    ElaAnalyzer,
)
from document_intelligence.modules.forensics.application.processing_service import (
    ForensicProcessingService,
)
from document_intelligence.modules.forensics.interfaces.registry import (
    AnalyzerRegistry,
    default_registry,
)
from document_intelligence.modules.graph.service import EvidenceGraphService
from document_intelligence.modules.relationship_detection.service import (
    RelationshipDetectionService,
)
from document_intelligence.modules.understanding.service import DocumentUnderstandingService


def get_settings() -> Settings:
    """Retrieve global settings."""
    return settings


def get_storage(app_settings: Settings = Depends(get_settings)) -> DocumentStorageProtocol:
    """Retrieve storage implementation."""
    return FilesystemDocumentStorage(app_settings=app_settings)


def get_audit_service(db: Session = Depends(get_db)) -> AuditLedgerService:
    """Retrieve audit ledger service."""
    repo = AuditRepository(db)
    return AuditLedgerService(repo)


def get_case_service(
    db: Session = Depends(get_db),
    audit_service: AuditLedgerService = Depends(get_audit_service),
) -> CaseService:
    """Retrieve Case service."""
    case_repo = CaseRepository(db)
    return CaseService(case_repo=case_repo, audit_service=audit_service)


def get_document_service(
    db: Session = Depends(get_db),
    storage: DocumentStorageProtocol = Depends(get_storage),
    audit_service: AuditLedgerService = Depends(get_audit_service),
    app_settings: Settings = Depends(get_settings),
) -> DocumentService:
    """Retrieve Document service."""
    case_repo = CaseRepository(db)
    doc_repo = DocumentRepository(db)
    return DocumentService(
        case_repo=case_repo,
        document_repo=doc_repo,
        storage=storage,
        audit_service=audit_service,
        app_settings=app_settings,
    )


def get_document_repository(db: Session = Depends(get_db)) -> DocumentRepository:
    """Retrieve Document repository."""
    return DocumentRepository(db)


def get_finding_repository(db: Session = Depends(get_db)) -> FindingRepository:
    """Retrieve Finding repository."""
    return FindingRepository(db)


def get_processing_run_repository(db: Session = Depends(get_db)) -> ProcessingRunRepository:
    """Retrieve ProcessingRun repository."""
    return ProcessingRunRepository(db)


def get_evidence_repository(db: Session = Depends(get_db)) -> EvidenceRepository:
    """Retrieve Evidence repository."""
    return EvidenceRepository(db)


def get_analyzer_registry() -> AnalyzerRegistry:
    """Retrieve global analyzer registry, ensuring standard adapters are registered."""
    if not default_registry.get("pdf-structural-analyzer"):
        default_registry.register(PdfStructuralAnalyzer())
    if not default_registry.get("ela-analyzer"):
        default_registry.register(ElaAnalyzer())
    if not default_registry.get("copy-move-analyzer"):
        default_registry.register(CopyMoveAnalyzer())
    if not default_registry.get("pdfium-ocr-engine"):
        default_registry.register(PdfiumOcrAdapter())
    if not default_registry.get("rapidocr-optical-engine"):
        default_registry.register(RapidOcrAdapter())
    if not default_registry.get("hybrid-ocr-pipeline"):
        default_registry.register(HybridOcrAdapter())
    if not default_registry.get("ppocrv5-devanagari-engine"):
        default_registry.register(DevanagariRapidOcrAdapter())
    return default_registry


def get_forensic_processing_service(
    db: Session = Depends(get_db),
    storage: DocumentStorageProtocol = Depends(get_storage),
    audit_service: AuditLedgerService = Depends(get_audit_service),
    registry: AnalyzerRegistry = Depends(get_analyzer_registry),
) -> ForensicProcessingService:
    """Retrieve ForensicProcessingService with dependencies wired."""
    return ForensicProcessingService(
        processing_run_repo=ProcessingRunRepository(db),
        evidence_repo=EvidenceRepository(db),
        finding_repo=FindingRepository(db),
        document_repo=DocumentRepository(db),
        case_repo=CaseRepository(db),
        audit_service=audit_service,
        storage=storage,
        registry=registry,
    )


def get_document_understanding_service(
    db: Session = Depends(get_db),
    storage: DocumentStorageProtocol = Depends(get_storage),
    audit_service: AuditLedgerService = Depends(get_audit_service),
    case_service: CaseService = Depends(get_case_service),
    forensic_service: ForensicProcessingService = Depends(get_forensic_processing_service),
) -> DocumentUnderstandingService:
    """Retrieve DocumentUnderstandingService with dependencies wired."""
    return DocumentUnderstandingService(
        case_service=case_service,
        document_repo=DocumentRepository(db),
        run_repo=ProcessingRunRepository(db),
        evidence_repo=EvidenceRepository(db),
        audit_service=audit_service,
        storage=storage,
        forensic_processing=forensic_service,
    )


def get_entity_resolution_service(
    db: Session = Depends(get_db),
    storage: DocumentStorageProtocol = Depends(get_storage),
    audit_service: AuditLedgerService = Depends(get_audit_service),
    case_service: CaseService = Depends(get_case_service),
    understanding_service: DocumentUnderstandingService = Depends(
        get_document_understanding_service
    ),
) -> EntityResolutionService:
    """Retrieve EntityResolutionService with dependencies wired."""
    return EntityResolutionService(
        case_service=case_service,
        document_repo=DocumentRepository(db),
        run_repo=ProcessingRunRepository(db),
        match_repo=EntityMatchRepository(db),
        storage=storage,
        audit_service=audit_service,
        understanding_service=understanding_service,
    )


def get_relationship_service(
    db: Session = Depends(get_db),
    storage: DocumentStorageProtocol = Depends(get_storage),
    audit_service: AuditLedgerService = Depends(get_audit_service),
    case_service: CaseService = Depends(get_case_service),
    understanding_service: DocumentUnderstandingService = Depends(
        get_document_understanding_service
    ),
    entity_resolution_service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> RelationshipDetectionService:
    """Retrieve RelationshipDetectionService with dependencies wired."""
    return RelationshipDetectionService(
        case_service=case_service,
        document_repo=DocumentRepository(db),
        run_repo=ProcessingRunRepository(db),
        relationship_repo=RelationshipRepository(db),
        storage=storage,
        audit_service=audit_service,
        entity_match_repo=EntityMatchRepository(db),
        entity_resolution_service=entity_resolution_service,
        understanding_service=understanding_service,
    )


def get_consistency_service(
    db: Session = Depends(get_db),
    storage: DocumentStorageProtocol = Depends(get_storage),
    audit_service: AuditLedgerService = Depends(get_audit_service),
    case_service: CaseService = Depends(get_case_service),
    understanding_service: DocumentUnderstandingService = Depends(
        get_document_understanding_service
    ),
    relationship_service: RelationshipDetectionService = Depends(get_relationship_service),
) -> ConsistencyAnalysisService:
    """Retrieve ConsistencyAnalysisService with dependencies wired."""
    return ConsistencyAnalysisService(
        case_service=case_service,
        document_repo=DocumentRepository(db),
        run_repo=ProcessingRunRepository(db),
        consistency_repo=ConsistencyRepository(db),
        storage=storage,
        audit_service=audit_service,
        understanding_service=understanding_service,
        entity_match_repo=EntityMatchRepository(db),
        relationship_repo=RelationshipRepository(db),
        evidence_repo=EvidenceRepository(db),
    )


def get_evidence_graph_service(
    db: Session = Depends(get_db),
) -> EvidenceGraphService:
    """Retrieve EvidenceGraphService with repositories wired."""
    return EvidenceGraphService(
        case_repo=CaseRepository(db),
        document_repo=DocumentRepository(db),
        evidence_repo=EvidenceRepository(db),
        finding_repo=FindingRepository(db),
        consistency_repo=ConsistencyRepository(db),
        relationship_repo=RelationshipRepository(db),
        entity_match_repo=EntityMatchRepository(db),
    )


def get_dossier_service(
    db: Session = Depends(get_db),
    audit_service: AuditLedgerService = Depends(get_audit_service),
) -> InvestigationDossierService:
    """Retrieve InvestigationDossierService with repositories and audit service wired."""
    return InvestigationDossierService(
        case_repo=CaseRepository(db),
        document_repo=DocumentRepository(db),
        finding_repo=FindingRepository(db),
        consistency_repo=ConsistencyRepository(db),
        relationship_repo=RelationshipRepository(db),
        entity_match_repo=EntityMatchRepository(db),
        evidence_repo=EvidenceRepository(db),
        dossier_repo=DossierRepository(db),
        audit_service=audit_service,
    )


def get_case_evidence_retriever(
    db: Session = Depends(get_db),
) -> CaseEvidenceRetriever:
    """Retrieve CaseEvidenceRetriever with repositories wired."""
    return CaseEvidenceRetriever(
        case_repo=CaseRepository(db),
        document_repo=DocumentRepository(db),
        finding_repo=FindingRepository(db),
        consistency_repo=ConsistencyRepository(db),
        relationship_repo=RelationshipRepository(db),
        entity_match_repo=EntityMatchRepository(db),
        evidence_repo=EvidenceRepository(db),
        dossier_repo=DossierRepository(db),
    )


def get_assistant_service(
    db: Session = Depends(get_db),
    retriever: CaseEvidenceRetriever = Depends(get_case_evidence_retriever),
    audit_service: AuditLedgerService = Depends(get_audit_service),
) -> AssistantService:
    """Retrieve AssistantService with retriever, configured provider, and audit ledger."""
    provider = get_llm_provider(settings)
    return AssistantService(
        retriever=retriever,
        provider=provider,
        audit_service=audit_service,
    )


# -----------------------------------------------------------------------------
# Authentication & Authorization Dependencies
# -----------------------------------------------------------------------------


def get_auth_repo(db: Session = Depends(get_db)) -> AuthRepository:
    """Retrieve authentication repository."""
    return AuthRepository(db)


def get_auth_service(repo: AuthRepository = Depends(get_auth_repo)) -> AuthenticationService:
    """Retrieve authentication service."""
    return AuthenticationService(repo=repo)


def get_case_access_service(repo: AuthRepository = Depends(get_auth_repo)) -> CaseAccessService:
    """Retrieve Case RBAC authorization service."""
    return CaseAccessService(repo=repo)


def get_cross_case_service(
    db: Session = Depends(get_db),
    case_access_service: CaseAccessService = Depends(get_case_access_service),
    case_service: CaseService = Depends(get_case_service),
    audit_service: AuditLedgerService = Depends(get_audit_service),
    entity_resolution_service: EntityResolutionService = Depends(get_entity_resolution_service),
) -> CrossCaseCorrelationService:
    """Retrieve Cross-Case Correlation and Investigation Intelligence service."""
    return CrossCaseCorrelationService(
        cross_case_repo=CrossCaseRepository(db),
        case_access_service=case_access_service,
        case_service=case_service,
        case_repo=CaseRepository(db),
        document_repo=DocumentRepository(db),
        evidence_repo=EvidenceRepository(db),
        finding_repo=FindingRepository(db),
        audit_service=audit_service,
        entity_resolution_service=entity_resolution_service,
    )


def get_current_user(
    request: Request,
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> UserModel:
    """Extract, verify, and authenticate user principal from Bearer header or session cookie."""
    token: str | None = None
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise AuthenticationException("Authentication required. Missing Bearer token or cookie.")

    payload = auth_service.token_service.decode_access_token(token)
    user = auth_service.repo.get_user_by_id(payload.sub)

    if not user or not user.is_active:
        raise AuthenticationException("User account not found or disabled.")

    return user


def require_case_access(
    min_role: CaseRole = CaseRole.VIEWER, is_mutation: bool = False
) -> Callable[..., CaseRole]:
    """Dependency factory enforcing case-scoped RBAC and archived case restrictions."""

    def _dependency(
        case_id: str,
        user: UserModel = Depends(get_current_user),
        access_service: CaseAccessService = Depends(get_case_access_service),
    ) -> CaseRole:
        return access_service.check_case_access(
            user=user,
            case_id=case_id,
            min_role=min_role,
            is_mutation=is_mutation,
        )

    return _dependency
