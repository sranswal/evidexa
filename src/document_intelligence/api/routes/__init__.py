"""API route exports."""

from fastapi import APIRouter

from document_intelligence.api.routes.audit import router as audit_router
from document_intelligence.api.routes.cases import router as cases_router
from document_intelligence.api.routes.documents import router as documents_router
from document_intelligence.api.routes.entity_resolution import (
    router as entity_resolution_router,
)
from document_intelligence.api.routes.findings import router as findings_router
from document_intelligence.api.routes.forensics import router as forensics_router
from document_intelligence.api.routes.health import router as health_router
from document_intelligence.api.routes.ocr import router as ocr_router
from document_intelligence.api.routes.relationships import (
    router as relationships_router,
)
from document_intelligence.api.routes.understanding import router as understanding_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(cases_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(findings_router)
api_v1_router.include_router(forensics_router)
api_v1_router.include_router(ocr_router)
api_v1_router.include_router(understanding_router)
api_v1_router.include_router(entity_resolution_router)
api_v1_router.include_router(relationships_router)
api_v1_router.include_router(audit_router)

__all__ = ["api_v1_router", "health_router"]
