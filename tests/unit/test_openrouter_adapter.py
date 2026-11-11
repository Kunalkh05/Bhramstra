"""
Unit tests for OpenRouter provider adapter using hermetic respx HTTP mocks.
"""

import pytest
import respx
import httpx
from brahmastra.infrastructure.providers.openrouter import OpenRouterAdapter
from brahmastra.domain.providers.models import GenerationRequest, ChatMessage
from brahmastra.domain.providers.exceptions import (
    AuthenticationError,
    RateLimitError,
)


@respx.mock
def test_openrouter_health_check_healthy():
    """Verify health check succeeds when OpenRouter returns 200."""
    respx.get("https://openrouter.ai/api/v1/models").respond(
        status_code=200,
        json={"data": []},
    )

    adapter = OpenRouterAdapter()
    health = adapter.health_check(secret="sk-test-token")
    assert health.status == "HEALTHY"
    assert health.latency_ms is not None
    assert health.latency_ms >= 0


@respx.mock
def test_openrouter_health_check_unreachable():
    """Verify health check returns UNREACHABLE on network error."""
    respx.get("https://openrouter.ai/api/v1/models").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    adapter = OpenRouterAdapter()
    health = adapter.health_check()
    assert health.status == "UNREACHABLE"
    assert "Health probe failed" in health.details


@respx.mock
def test_openrouter_list_models():
    """Verify parsing of OpenRouter models catalog."""
    respx.get("https://openrouter.ai/api/v1/models").respond(
        status_code=200,
        json={
            "data": [
                {
                    "id": "anthropic/claude-3.5-sonnet",
                    "name": "Claude 3.5 Sonnet",
                    "context_length": 200000,
                    "description": "Frontier intelligence",
                    "architecture": {"modality": "text+image->text"},
                },
                {
                    "id": "meta-llama/llama-3.1-8b-instruct",
                    "name": "Llama 3.1 8B",
                    "context_length": 131072,
                    "description": "Fast open model",
                    "architecture": {"modality": "text->text"},
                },
            ]
        },
    )

    adapter = OpenRouterAdapter()
    models = adapter.list_models(secret="sk-test")
    assert len(models) == 2

    claude = next(m for m in models if m.id == "anthropic/claude-3.5-sonnet")
    assert claude.context_window == 200000
    assert claude.is_local is False
    assert any(c.value == "vision" for c in claude.capabilities)


@respx.mock
def test_openrouter_generate_success():
    """Verify successful generation and token usage extraction."""
    respx.post("https://openrouter.ai/api/v1/chat/completions").respond(
        status_code=200,
        json={
            "id": "gen-123",
            "model": "anthropic/claude-3.5-sonnet",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello, world!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 5,
                "total_tokens": 17,
            },
        },
    )

    adapter = OpenRouterAdapter()
    req = GenerationRequest(
        model="anthropic/claude-3.5-sonnet",
        messages=[ChatMessage(role="user", content="Hi")],
    )
    res = adapter.generate(req, secret="sk-test-token")
    assert res.content == "Hello, world!"
    assert res.model == "anthropic/claude-3.5-sonnet"
    assert res.usage.prompt_tokens == 12
    assert res.usage.completion_tokens == 5
    assert res.usage.total_tokens == 17
    assert res.finish_reason == "stop"


def test_openrouter_generate_missing_secret_fails():
    """Verify generation fails if secret is missing."""
    adapter = OpenRouterAdapter()
    req = GenerationRequest(
        model="test-model",
        messages=[ChatMessage(role="user", content="Hi")],
    )
    with pytest.raises(AuthenticationError, match="requires a valid API key"):
        adapter.generate(req, secret=None)


@respx.mock
def test_openrouter_generate_auth_failure_401():
    """Verify 401 response maps to AuthenticationError."""
    respx.post("https://openrouter.ai/api/v1/chat/completions").respond(
        status_code=401,
        json={"error": {"message": "Invalid API Key"}},
    )

    adapter = OpenRouterAdapter()
    req = GenerationRequest(
        model="test-model",
        messages=[ChatMessage(role="user", content="Hi")],
    )
    with pytest.raises(AuthenticationError, match="authentication failed"):
        adapter.generate(req, secret="invalid-token")


@respx.mock
def test_openrouter_generate_rate_limit_429():
    """Verify 429 response maps to RateLimitError."""
    respx.post("https://openrouter.ai/api/v1/chat/completions").respond(
        status_code=429,
        json={"error": {"message": "Rate limit exceeded"}},
    )

    adapter = OpenRouterAdapter()
    req = GenerationRequest(
        model="test-model",
        messages=[ChatMessage(role="user", content="Hi")],
    )
    with pytest.raises(RateLimitError, match="rate limit or quota exceeded"):
        adapter.generate(req, secret="valid-token")
