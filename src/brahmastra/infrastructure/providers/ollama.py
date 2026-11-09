"""
Ollama local runtime provider adapter.
"""

import time
from typing import List, Optional
import httpx

from brahmastra.domain.providers.interface import ProviderInterface
from brahmastra.domain.providers.models import (
    GenerationRequest,
    GenerationResponse,
    GenerationUsage,
    ModelInfo,
    ModelCapability,
    HealthStatus,
)
from brahmastra.domain.providers.exceptions import (
    ProviderUnavailableError,
    TimeoutError,
    InvalidRequestError,
    ProviderError,
)

DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434"


class OllamaAdapter(ProviderInterface):
    """
    Adapter for Ollama local runtime executing on macOS Apple Silicon (M1/M2/M3) and Intel.
    Requires zero internet connection and zero API keys.
    """

    def __init__(self, endpoint: Optional[str] = None, timeout: float = 60.0):
        self.endpoint = (endpoint or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        self.timeout = timeout

    @property
    def provider_type(self) -> str:
        return "ollama"

    def _handle_http_error(self, exc: Exception) -> None:
        """Map local daemon errors to normalized domain exceptions."""
        if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
            raise ProviderUnavailableError(
                f"Ollama local runtime is not running at {self.endpoint}. "
                "Start Ollama via the macOS application or run 'ollama serve'.",
                provider="ollama",
            )
        if isinstance(exc, (httpx.TimeoutException, httpx.ReadTimeout)):
            raise TimeoutError(
                f"Ollama request timed out after {self.timeout}s.",
                provider="ollama",
            )
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            detail = exc.response.text
            if code == 404:
                raise InvalidRequestError(
                    f"Model not found in local Ollama repository. Run 'ollama pull <model>' first.",
                    provider="ollama",
                    status_code=404,
                )
            raise ProviderError(
                f"Ollama error (HTTP {code}): {detail}",
                provider="ollama",
                status_code=code,
            )

    def generate(
        self,
        request: GenerationRequest,
        secret: Optional[str] = None,
    ) -> GenerationResponse:
        url = f"{self.endpoint}/api/chat"
        options = {
            "temperature": request.temperature,
        }
        if request.max_tokens:
            options["num_predict"] = request.max_tokens

        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
            "options": options,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()

            message = data.get("message", {})
            content = message.get("content", "")
            finish_reason = data.get("done_reason") or ("stop" if data.get("done") else None)

            usage = GenerationUsage(
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
                total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            )

            return GenerationResponse(
                content=content,
                model=data.get("model", request.model),
                usage=usage,
                finish_reason=finish_reason,
            )
        except Exception as exc:
            self._handle_http_error(exc)
            raise

    def list_models(self, secret: Optional[str] = None) -> List[ModelInfo]:
        url = f"{self.endpoint}/api/tags"
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url)
                res.raise_for_status()
                data = res.json()

            models: List[ModelInfo] = []
            for item in data.get("models", []):
                model_name = item.get("name")
                details = item.get("details", {})
                param_size = details.get("parameter_size", "unknown")
                family = details.get("family", "")

                models.append(
                    ModelInfo(
                        id=model_name,
                        name=f"{model_name} ({param_size})",
                        provider="ollama",
                        context_window=4096,
                        capabilities=[
                            ModelCapability.CHAT,
                            ModelCapability.STREAMING,
                            ModelCapability.JSON_OUTPUT,
                        ],
                        is_local=True,
                        description=f"Local {family} model ({param_size})",
                    )
                )
            return models
        except Exception as exc:
            self._handle_http_error(exc)
            raise

    def health_check(self, secret: Optional[str] = None) -> HealthStatus:
        url = f"{self.endpoint}/api/tags"
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(url)
                res.raise_for_status()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return HealthStatus(
                status="HEALTHY",
                latency_ms=round(elapsed_ms, 2),
                details=f"Ollama local runtime reachable at {self.endpoint}",
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return HealthStatus(
                status="UNREACHABLE",
                latency_ms=round(elapsed_ms, 2),
                details="Ollama is not running locally. Start it with 'ollama serve'.",
            )
