"""Unit tests for HttpLlmProvider reliability, bounded resource usage, and error discrimination."""

from __future__ import annotations

import contextlib

import httpx
import pytest

from document_intelligence.modules.assistant.provider import (
    MAX_REQUEST_SIZE_BYTES,
    MAX_RESPONSE_SIZE_BYTES,
    HttpLlmProvider,
    ProviderConnectionError,
    ProviderPayloadLimitError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)


class DummyStreamResponse:
    def __init__(
        self,
        status_code: int = 200,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
        reason_phrase: str = "OK",
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.reason_phrase = reason_phrase

    def iter_bytes(self, chunk_size: int = 8192):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]


def test_provider_rejects_oversized_request_payload() -> None:
    provider = HttpLlmProvider(api_base="http://localhost:11434")

    # Generate oversized system prompt exceeding MAX_REQUEST_SIZE_BYTES
    huge_prompt = "A" * (MAX_REQUEST_SIZE_BYTES + 1024)

    with pytest.raises(ProviderPayloadLimitError) as exc_info:
        provider.generate(system_prompt=huge_prompt, user_prompt="test")

    assert "exceeds limit" in str(exc_info.value)


def test_provider_handles_connect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = HttpLlmProvider(api_base="http://192.0.2.1:8080", timeout_seconds=1.0, max_retries=0)

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        raise httpx.ConnectTimeout("Connection timed out to test host")
        yield

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderTimeoutError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "Connection timeout" in str(exc_info.value)


def test_provider_handles_read_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = HttpLlmProvider(api_base="http://localhost:8080", timeout_seconds=1.0, max_retries=0)

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        raise httpx.ReadTimeout("Read timed out waiting for generation")
        yield

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderTimeoutError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "Read/write timeout" in str(exc_info.value)


def test_provider_handles_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = HttpLlmProvider(api_base="http://unreachable-host:9999", max_retries=0)

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        raise httpx.ConnectError("Failed to establish connection")
        yield

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderConnectionError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "Failed to connect" in str(exc_info.value)


def test_provider_handles_rate_limiting_429(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = HttpLlmProvider(api_base="http://localhost:8080", max_retries=0)

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        yield DummyStreamResponse(status_code=429, headers={"Retry-After": "1"})

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderRateLimitError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "rate limit exceeded" in str(exc_info.value).lower()


def test_provider_handles_server_error_500(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = HttpLlmProvider(api_base="http://localhost:8080", max_retries=0)

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        yield DummyStreamResponse(status_code=500, reason_phrase="Internal Server Error")

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderResponseError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "HTTP 500" in str(exc_info.value)


def test_provider_handles_empty_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = HttpLlmProvider(api_base="http://localhost:8080", max_retries=0)

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        yield DummyStreamResponse(status_code=200, content=b'{"choices": []}')

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderResponseError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "missing 'choices'" in str(exc_info.value).lower()


def test_provider_early_aborts_on_oversized_content_length(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies response limits are enforced before fully buffering via Content-Length header."""
    provider = HttpLlmProvider(api_base="http://localhost:8080", max_retries=0)

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        yield DummyStreamResponse(
            status_code=200,
            content=b"",
            headers={"Content-Length": str(MAX_RESPONSE_SIZE_BYTES + 10000)},
        )

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderPayloadLimitError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "exceeds limit" in str(exc_info.value).lower()


def test_provider_early_aborts_on_oversized_streamed_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies response limits are enforced during chunk iteration before unbounded memory usage."""
    provider = HttpLlmProvider(api_base="http://localhost:8080", max_retries=0)

    oversized_bytes = b"X" * (MAX_RESPONSE_SIZE_BYTES + 4096)

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        yield DummyStreamResponse(status_code=200, content=oversized_bytes)

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderPayloadLimitError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "exceeded size limit" in str(exc_info.value).lower()


def test_provider_does_not_blindly_retry_401_or_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies non-retryable 4xx client errors (401, 403, 404) fail fast without retries."""
    provider = HttpLlmProvider(api_base="http://localhost:8080", max_retries=2)
    call_count = 0

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield DummyStreamResponse(status_code=401, reason_phrase="Unauthorized")

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderResponseError) as exc_info:
        provider.generate(system_prompt="sys", user_prompt="user")

    assert "HTTP 401" in str(exc_info.value)
    # Must fail on attempt 1 without retrying
    assert call_count == 1


def test_provider_error_does_not_expose_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies authorization keys and raw prompts are not leaked in error exceptions."""
    secret_key = "sk-SUPER-SECRET-API-KEY-DO-NOT-LEAK"
    provider = HttpLlmProvider(
        api_base="http://localhost:8080",
        api_key=secret_key,
        max_retries=0,
    )

    @contextlib.contextmanager
    def mock_stream(*args, **kwargs):
        yield DummyStreamResponse(status_code=403, reason_phrase="Forbidden")

    monkeypatch.setattr(httpx.Client, "stream", mock_stream)

    with pytest.raises(ProviderResponseError) as exc_info:
        provider.generate(system_prompt="classified prompt", user_prompt="secret inquiry")

    error_text = str(exc_info.value)
    assert secret_key not in error_text
    assert "classified prompt" not in error_text
