"""Unit tests verifying Runtime AI Configuration & Gemini Multimodal Analyzer."""

from pathlib import Path
from unittest.mock import patch

from document_intelligence.api.dependencies import get_analyzer_registry
from document_intelligence.core.ai_config import AiConfigManager, mask_api_key
from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.modules.forensics.adapters.visual.gemini_analyzer import (
    GeminiMultimodalAnalyzer,
)
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput


def test_mask_api_key_utility() -> None:
    assert mask_api_key(None) is None
    assert mask_api_key("") is None
    assert mask_api_key("short") == "****"
    assert mask_api_key("AIzaSyD123456789XyZ") == "AIzaSy...9XyZ"


def test_ai_config_manager_offline_by_default() -> None:
    mgr = AiConfigManager()
    cfg = mgr.get_public_config()
    assert "mode" in cfg
    assert "available_models" in cfg
    assert len(cfg["available_models"]) >= 4


def test_ai_config_manager_switch_modes() -> None:
    mgr = AiConfigManager()
    # Switch to offline
    res_off = mgr.update_config(mode="OFFLINE", model="gemini-3.8-flash")
    assert res_off["success"] is True
    assert mgr.mode == "OFFLINE"
    assert mgr.is_online is False

    # Switch to online without key should fail
    res_fail = mgr.update_config(mode="ONLINE", api_key="", model="gemini-3.8-flash")
    assert res_fail["success"] is False
    assert "required" in res_fail["error"]

    # Switch to online with key and mock validation
    with patch.object(
        mgr, "test_gemini_connection", return_value={"success": True, "latency_ms": 120.5}
    ):
        res_on = mgr.update_config(
            mode="ONLINE",
            api_key="AIzaSyTestMockKey12345",
            model="gemini-3.8-flash",
            validate=True,
        )
        assert res_on["success"] is True
        assert mgr.mode == "ONLINE"
        assert mgr.is_online is True
        pub = mgr.get_public_config()
        assert pub["has_key"] is True
        assert pub["masked_key"] == "AIzaSy...2345"


def test_gemini_analyzer_registered() -> None:
    registry = get_analyzer_registry()
    analyzer = registry.get("gemini-multimodal-analyzer")
    assert analyzer is not None
    assert isinstance(analyzer, GeminiMultimodalAnalyzer)
    assert analyzer.can_analyze("application/pdf")
    assert analyzer.can_analyze("image/png")
    assert analyzer.can_analyze("image/jpeg")


def test_gemini_analyzer_offline_graceful_limitation(tmp_path: Path) -> None:
    test_file = tmp_path / "sample.png"
    test_file.write_bytes(b"\x89PNG\r\n\x1a\nfakecontent")

    analyzer = GeminiMultimodalAnalyzer()
    inp = AnalyzerInput(
        file_path=str(test_file),
        detected_media_type="image/png",
        document_id="doc-test-1",
        case_id="case-test-1",
        processing_run_id="run-test-1",
        document_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    )

    # In offline mode, analyzer should succeed and return informative limitation observation
    out = analyzer.analyze(inp)
    assert out.status == PipelineStatus.SUCCEEDED
    assert len(out.observations) == 1
    assert "Inactive" in out.observations[0].title
