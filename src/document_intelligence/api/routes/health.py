"""Health check endpoints."""

from typing import Any

from fastapi import APIRouter

from document_intelligence.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=dict[str, Any])
@router.get("/api/v1/health", response_model=dict[str, Any])
async def health_check() -> dict[str, Any]:
    """Return platform operational status and version."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }
