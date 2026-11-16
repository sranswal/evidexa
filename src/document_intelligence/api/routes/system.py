"""System and AI runtime configuration endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from document_intelligence.api.dependencies import get_current_user
from document_intelligence.core.ai_config import ai_config_manager
from document_intelligence.infrastructure.persistence.models import UserModel

router = APIRouter(prefix="/system", tags=["System & AI Engine"])


class UpdateAiConfigRequest(BaseModel):
    """Payload to update runtime AI configuration."""

    mode: Literal["OFFLINE", "ONLINE"] = Field(
        description="Operating mode: OFFLINE (Air-gapped deterministic) or ONLINE (Gemini Multimodal AI)"
    )
    provider: str = Field(default="gemini", description="AI Provider (default: gemini)")
    model: str = Field(default="gemini-3.8-flash", description="Target model identifier")
    api_key: str | None = Field(default=None, description="Google Gemini API Key")
    auto_validate: bool = Field(
        default=True,
        alias="validate",
        description="Whether to test the key immediately upon update",
    )


class TestAiKeyRequest(BaseModel):
    """Payload to test a Gemini API key without changing state."""

    api_key: str = Field(description="Google Gemini API key to validate")
    model: str = Field(default="gemini-3.8-flash", description="Target model for test ping")


@router.get("/ai-config", response_model=dict[str, Any])
async def get_ai_configuration(
    _: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve active AI engine configuration and operating mode."""
    return ai_config_manager.get_public_config()


@router.post("/ai-config", response_model=dict[str, Any])
async def update_ai_configuration(
    payload: UpdateAiConfigRequest,
    _: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Update runtime AI engine configuration (switch between Offline and Online modes)."""
    return ai_config_manager.update_config(
        mode=payload.mode,
        provider=payload.provider,
        model=payload.model,
        api_key=payload.api_key,
        validate=payload.auto_validate,
    )


@router.post("/ai-config/test", response_model=dict[str, Any])
async def test_ai_key(
    payload: TestAiKeyRequest,
    _: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Test a Google Gemini API key and measure latency."""
    return ai_config_manager.test_gemini_connection(
        api_key=payload.api_key,
        model=payload.model,
    )
