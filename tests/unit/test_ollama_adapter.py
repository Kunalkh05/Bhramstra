"""
Unit tests for Ollama local provider adapter using respx HTTP mocks.
"""

import pytest
import respx
import httpx
from brahmastra.infrastructure.providers.ollama import OllamaAdapter
from brahmastra.domain.providers.models import GenerationRequest, ChatMessage
from brahmastra.domain.providers.exceptions import (
    ProviderUnavailableError,
    InvalidRequestError,
)


@respx.mock
def test_ollama_health_check_healthy():
    """Verify health check succeeds when local daemon responds."""
    respx.get("http://localhost:11434/api/tags").respond(
        status_code=200,
        json={"models": []},
    )

    adapter = OllamaAdapter()
    health = adapter.health_check()
    assert health.status == "HEALTHY"
    assert health.latency_ms is not None


@respx.mock
def test_ollama_health_check_daemon_down():
    """Verify health check returns UNREACHABLE with helpful remediation when daemon is down."""
    respx.get("http://localhost:11434/api/tags").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    adapter = OllamaAdapter()
    health = adapter.health_check()
    assert health.status == "UNREACHABLE"
    assert "ollama serve" in health.details


@respx.mock
def test_ollama_list_models():
    """Verify parsing local Ollama models list."""
    respx.get("http://localhost:11434/api/tags").respond(
        status_code=200,
        json={
            "models": [
                {
                    "name": "llama3:latest",
                    "details": {"parameter_size": "8.0B", "family": "llama"},
                },
                {
                    "name": "qwen2.5-coder:7b",
                    "details": {"parameter_size": "7.6B", "family": "qwen2"},
                },
            ]
        },
    )

    adapter = OllamaAdapter()
    models = adapter.list_models()
    assert len(models) == 2

    llama = next(m for m in models if "llama3" in m.id)
    assert llama.is_local is True
    assert llama.provider == "ollama"
    assert "8.0B" in llama.name


@respx.mock
def test_ollama_generate_success():
    """Verify generation against local Ollama runtime."""
    respx.post("http://localhost:11434/api/chat").respond(
        status_code=200,
        json={
            "model": "llama3",
            "message": {"role": "assistant", "content": "Local AI reply"},
            "done_reason": "stop",
            "prompt_eval_count": 8,
            "eval_count": 6,
        },
    )

    adapter = OllamaAdapter()
    req = GenerationRequest(
        model="llama3",
        messages=[ChatMessage(role="user", content="Test")],
    )
    res = adapter.generate(req)
    assert res.content == "Local AI reply"
    assert res.model == "llama3"
    assert res.usage.prompt_tokens == 8
    assert res.usage.completion_tokens == 6
    assert res.usage.total_tokens == 14
    assert res.finish_reason == "stop"


@respx.mock
def test_ollama_generate_model_not_found_404():
    """Verify 404 maps to InvalidRequestError with pull instruction."""
    respx.post("http://localhost:11434/api/chat").respond(
        status_code=404,
        text="model not found",
    )

    adapter = OllamaAdapter()
    req = GenerationRequest(
        model="nonexistent-model",
        messages=[ChatMessage(role="user", content="Test")],
    )
    with pytest.raises(InvalidRequestError, match="ollama pull"):
        adapter.generate(req)


@respx.mock
def test_ollama_daemon_connection_failure():
    """Verify connection refusal maps to ProviderUnavailableError."""
    respx.post("http://localhost:11434/api/chat").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    adapter = OllamaAdapter()
    req = GenerationRequest(
        model="llama3",
        messages=[ChatMessage(role="user", content="Test")],
    )
    with pytest.raises(ProviderUnavailableError, match="Ollama local runtime is not running"):
        adapter.generate(req)
