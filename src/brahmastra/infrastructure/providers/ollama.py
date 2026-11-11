"""
Ollama local runtime provider adapter.
"""

import time
import urllib.parse
import ipaddress
import socket
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
        raw_endpoint = (endpoint or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        parsed = urllib.parse.urlsplit(raw_endpoint)

        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Invalid endpoint scheme '{parsed.scheme}'. Only 'http' and 'https' are allowed (BRAH-SEC-005)."
            )

        raw_host = (parsed.hostname or "").lower()
        if not raw_host:
            raise ValueError("Endpoint host cannot be empty (BRAH-SEC-005).")

        # Explicit blocklist for known cloud metadata hostname aliases
        if raw_host in (
            "169.254.169.254",
            "metadata.google.internal",
            "metadata.internal",
            "instance-data",
        ):
            raise ValueError(
                f"Access to cloud metadata endpoints ({raw_host}) is forbidden (BRAH-SEC-005 SSRF protection)."
            )

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        ip_candidates = []

        # 1. Check for integer, hex, or octal IP representations (e.g. 2852039166, 0xa9fea9fe)
        try:
            int_val = int(raw_host, 0)
            if 0 <= int_val <= 0xFFFFFFFF:
                ip_candidates.append(ipaddress.IPv4Address(int_val))
        except (ValueError, TypeError):
            pass

        # 2. Check for direct IPv4 or IPv6 literal
        cleaned_host = raw_host.strip("[]")
        try:
            direct_ip = ipaddress.ip_address(cleaned_host)
            ip_candidates.append(direct_ip)
        except ValueError:
            pass

        # 3. DNS resolution via socket.getaddrinfo to resolve hostnames and aliases (e.g. nip.io)
        try:
            addr_info = socket.getaddrinfo(raw_host, port, proto=socket.IPPROTO_TCP)
            for entry in addr_info:
                sockaddr = entry[4]
                ip_str = sockaddr[0]
                try:
                    resolved_ip = ipaddress.ip_address(ip_str)
                    ip_candidates.append(resolved_ip)
                except ValueError:
                    pass
        except (socket.gaierror, OSError):
            pass

        # 4. Strict Network Policy Evaluation
        for ip in ip_candidates:
            # Handle IPv4-mapped IPv6 addresses (::ffff:169.254.169.254)
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                ip = ip.ipv4_mapped

            # Allow local loopback addresses for Ollama daemon
            if ip.is_loopback:
                continue

            # Reject AWS IMDS IPv6 (fd00:ec2::254)
            if str(ip) == "fd00:ec2::254":
                raise ValueError(
                    f"Access to cloud metadata endpoints ({ip}) is forbidden (BRAH-SEC-005 SSRF protection)."
                )

            # Reject link-local cloud metadata addresses (169.254.0.0/16, fe80::/10)
            if ip.is_link_local:
                raise ValueError(
                    f"Access to link-local cloud metadata endpoints ({ip}) is forbidden (BRAH-SEC-005 SSRF protection)."
                )

            # Reject private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
            if ip.is_private:
                raise ValueError(
                    f"Access to private internal network addresses ({ip}) is prohibited (BRAH-SEC-005 SSRF protection)."
                )

            # Reject multicast, reserved, or unspecified destinations
            if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                raise ValueError(
                    f"Access to reserved or multicast network destinations ({ip}) is prohibited (BRAH-SEC-005 SSRF protection)."
                )

        self.endpoint = raw_endpoint
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
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
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
            with httpx.Client(timeout=10.0, follow_redirects=False) as client:
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
            with httpx.Client(timeout=5.0, follow_redirects=False) as client:
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
