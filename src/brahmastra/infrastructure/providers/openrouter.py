"""
OpenRouter API provider adapter.
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
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
    TimeoutError,
    InvalidRequestError,
    ProviderError,
)

DEFAULT_OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(ProviderInterface):
    """
    Adapter integrating with OpenRouter's OpenAI-compatible unified API.
    """

    def __init__(self, endpoint: Optional[str] = None, timeout: float = 30.0):
        self.endpoint = (endpoint or DEFAULT_OPENROUTER_ENDPOINT).rstrip("/")
        self.timeout = timeout

    @property
    def provider_type(self) -> str:
        return "openrouter"

    def _get_headers(self, secret: Optional[str]) -> dict:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://brahmastra.ai",
            "X-Title": "BRAHMASTRA AI",
        }
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
        return headers

    def _handle_http_error(self, exc: Exception) -> None:
        """Map HTTP / transport exceptions to normalized domain exceptions."""
        if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
            raise ProviderUnavailableError(
                f"Failed to connect to OpenRouter endpoint ({self.endpoint}): Network unreachable.",
                provider="openrouter",
            )
        if isinstance(exc, (httpx.TimeoutException, httpx.ReadTimeout)):
            raise TimeoutError(
                f"OpenRouter request timed out after {self.timeout}s.",
                provider="openrouter",
            )
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            detail = ""
            try:
                body = exc.response.json()
                detail = body.get("error", {}).get("message") or str(body)
            except Exception:
                detail = exc.response.text

            if code in (401, 403):
                raise AuthenticationError(
                    f"OpenRouter authentication failed (HTTP {code}): {detail}",
                    provider="openrouter",
                    status_code=code,
                )
            if code == 429:
                raise RateLimitError(
                    f"OpenRouter rate limit or quota exceeded (HTTP 429): {detail}",
                    provider="openrouter",
                    status_code=code,
                )
            if code == 400:
                raise InvalidRequestError(
                    f"Invalid request to OpenRouter (HTTP 400): {detail}",
                    provider="openrouter",
                    status_code=code,
                )
            if code >= 500:
                raise ProviderUnavailableError(
                    f"OpenRouter service error (HTTP {code}): {detail}",
                    provider="openrouter",
                    status_code=code,
                )
            raise ProviderError(
                f"OpenRouter error (HTTP {code}): {detail}",
                provider="openrouter",
                status_code=code,
            )

    def generate(
        self,
        request: GenerationRequest,
        secret: Optional[str] = None,
    ) -> GenerationResponse:
        if not secret:
            raise AuthenticationError(
                "OpenRouter requires a valid API key credential.",
                provider="openrouter",
                status_code=401,
            )

        url = f"{self.endpoint}/chat/completions"
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "stream": request.stream,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, headers=self._get_headers(secret), json=payload)
                res.raise_for_status()
                data = res.json()

            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")

            usage_data = data.get("usage", {})
            usage = GenerationUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
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
        url = f"{self.endpoint}/models"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._get_headers(secret))
                res.raise_for_status()
                data = res.json()

            models: List[ModelInfo] = []
            for item in data.get("data", []):
                model_id = item.get("id")
                name = item.get("name") or model_id
                context_length = item.get("context_length") or 4096
                description = item.get("description")

                capabilities = [ModelCapability.CHAT]
                arch = item.get("architecture", {})
                modality = arch.get("modality", "")
                if "multimodal" in modality or "image" in modality:
                    capabilities.append(ModelCapability.VISION)
                capabilities.append(ModelCapability.STREAMING)

                models.append(
                    ModelInfo(
                        id=model_id,
                        name=name,
                        provider="openrouter",
                        context_window=context_length,
                        capabilities=capabilities,
                        is_local=False,
                        description=description,
                    )
                )
            return models
        except Exception as exc:
            self._handle_http_error(exc)
            raise

    def health_check(self, secret: Optional[str] = None) -> HealthStatus:
        url = f"{self.endpoint}/models"
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url, headers=self._get_headers(secret))
                res.raise_for_status()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return HealthStatus(
                status="HEALTHY",
                latency_ms=round(elapsed_ms, 2),
                details=f"OpenRouter reachable at {self.endpoint}",
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return HealthStatus(
                status="UNREACHABLE",
                latency_ms=round(elapsed_ms, 2),
                details=f"Health probe failed: {exc}",
            )
