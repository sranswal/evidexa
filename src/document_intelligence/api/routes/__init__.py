"""API route exports."""

from fastapi import APIRouter

from document_intelligence.api.routes.assistant import router as assistant_router
from document_intelligence.api.routes.audit import router as audit_router
from document_intelligence.api.routes.auth import (
    members_router as case_members_router,
)
from document_intelligence.api.routes.auth import (
    router as auth_router,
)
from document_intelligence.api.routes.cases import router as cases_router
from document_intelligence.api.routes.consistency import router as consistency_router
from document_intelligence.api.routes.cross_case import router as cross_case_router
from document_intelligence.api.routes.documents import router as documents_router
from document_intelligence.api.routes.dossier import router as dossier_router
from document_intelligence.api.routes.entity_resolution import (
    router as entity_resolution_router,
)
from document_intelligence.api.routes.findings import router as findings_router
from document_intelligence.api.routes.forensics import router as forensics_router
from document_intelligence.api.routes.graph import router as graph_router
from document_intelligence.api.routes.health import router as health_router
from document_intelligence.api.routes.ocr import router as ocr_router
from document_intelligence.api.routes.organizations import router as organizations_router
from document_intelligence.api.routes.relationships import (
    router as relationships_router,
)
from document_intelligence.api.routes.understanding import router as understanding_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(case_members_router)
api_v1_router.include_router(cross_case_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(findings_router)
api_v1_router.include_router(forensics_router)
api_v1_router.include_router(ocr_router)
api_v1_router.include_router(understanding_router)
api_v1_router.include_router(entity_resolution_router)
api_v1_router.include_router(relationships_router)
api_v1_router.include_router(consistency_router)
api_v1_router.include_router(graph_router)
api_v1_router.include_router(dossier_router)
api_v1_router.include_router(assistant_router)
api_v1_router.include_router(audit_router)

__all__ = ["api_v1_router", "health_router"]
