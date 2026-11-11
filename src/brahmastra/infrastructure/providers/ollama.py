"""
Ollama local runtime provider adapter with socket-level SSRF and DNS rebinding protection (BRAH-SEC-005).
"""

import time
import urllib.parse
import ipaddress
import socket
from typing import List, Optional, Iterable, Any
import httpcore
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

# Explicit set of hostnames that are strictly recognized as local loopback
ALLOWED_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "[::1]"}

# Blocklist for known cloud metadata hostnames and aliases
BLOCKED_METADATA_HOSTNAMES = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
    "100.100.100.200",
}

# Blocklist for dangerous network ranges
FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),    # CGNAT (including Alibaba Cloud metadata 100.100.100.200)
    ipaddress.ip_network("64:ff9b::/96"),      # NAT64
    ipaddress.ip_network("64:ff9b:1::/48"),    # Local-use NAT64
    ipaddress.ip_network("2002::/16"),         # 6to4
    ipaddress.ip_network("2001::/32"),         # Teredo
]


def validate_destination_ip(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    is_declared_local: bool = False,
) -> None:
    """
    Validate that an IP address complies with SSRF restrictions (BRAH-SEC-005).

    Blocks private, link-local, cloud metadata, multicast, reserved, unspecified,
    CGNAT, NAT64, 6to4, and Teredo ranges. Restricts loopback addresses solely to
    explicitly declared local hostnames to prevent DNS rebinding attacks.
    """
    # Unpack IPv4-mapped IPv6 addresses (e.g. ::ffff:169.254.169.254)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    # Recursively unwrap and validate 6to4 embedded IPv4 (2002::/16)
    if isinstance(ip, ipaddress.IPv6Address) and ip in ipaddress.IPv6Network("2002::/16"):
        embedded_6to4 = ipaddress.IPv4Address(ip.packed[2:6])
        validate_destination_ip(embedded_6to4, is_declared_local=is_declared_local)
        return

    # Recursively unwrap and validate Teredo embedded IPv4 (2001::/32)
    if isinstance(ip, ipaddress.IPv6Address) and ip in ipaddress.IPv6Network("2001::/32"):
        embedded_teredo = ipaddress.IPv4Address(bytes([b ^ 0xFF for b in ip.packed[12:16]]))
        validate_destination_ip(embedded_teredo, is_declared_local=is_declared_local)
        return

    # Strict loopback policy: loopback is only permitted for declared local hostnames
    if ip.is_loopback:
        if not is_declared_local:
            raise ValueError(
                f"DNS rebinding attack detected: Host resolved to loopback address ({ip}) "
                "but was not declared as a local loopback hostname (BRAH-SEC-005)."
            )
        return

    # Explicit cloud metadata IPs
    if str(ip) in ("169.254.169.254", "100.100.100.200", "fd00:ec2::254"):
        raise ValueError(
            f"Access to cloud metadata destination ({ip}) is forbidden (BRAH-SEC-005 SSRF protection)."
        )

    # Link-local addresses (169.254.0.0/16, fe80::/10)
    if ip.is_link_local:
        raise ValueError(
            f"Access to link-local cloud metadata destination ({ip}) is forbidden (BRAH-SEC-005 SSRF protection)."
        )

    # Private internal networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
    if ip.is_private:
        raise ValueError(
            f"Access to private internal network destination ({ip}) is prohibited (BRAH-SEC-005 SSRF protection)."
        )

    # Multicast, reserved, unspecified, broadcast
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified or (
        isinstance(ip, ipaddress.IPv4Address) and ip == ipaddress.IPv4Address("255.255.255.255")
    ):
        raise ValueError(
            f"Access to reserved or multicast network destination ({ip}) is prohibited (BRAH-SEC-005 SSRF protection)."
        )

    # Check against additional forbidden ranges (CGNAT, NAT64)
    for forbidden_net in FORBIDDEN_NETWORKS[:3]:
        if ip in forbidden_net:
            raise ValueError(
                f"Access to forbidden network range {forbidden_net} ({ip}) is prohibited (BRAH-SEC-005 SSRF protection)."
            )


class SSRFProtectingBackend(httpcore.SyncBackend):
    """
    Custom httpcore network backend that validates destination IPs at connection
    time and pins the connection to the validated numeric IP string to prevent
    DNS rebinding / TOCTOU attacks.
    """

    def __init__(self, is_declared_local: bool = True):
        super().__init__()
        self.is_declared_local = is_declared_local

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[Any]] = None,
    ) -> httpcore.NetworkStream:
        clean_host = host.strip("[]").lower()
        if clean_host in BLOCKED_METADATA_HOSTNAMES:
            raise httpcore.ConnectError(
                f"SSRF Protection: Access to metadata hostname '{host}' blocked (BRAH-SEC-005)."
            )

        # Resolve host to candidate IP addresses at socket creation time
        try:
            addr_info = socket.getaddrinfo(clean_host, port, proto=socket.IPPROTO_TCP)
        except Exception as exc:
            raise httpcore.ConnectError(
                f"SSRF Protection: Failed to resolve host '{host}': {exc}"
            ) from exc

        if not addr_info:
            raise httpcore.ConnectError(
                f"SSRF Protection: Host '{host}' resolved to no addresses."
            )

        # Validate every candidate address against SSRF policies
        valid_candidates: list[str] = []
        for entry in addr_info:
            sockaddr = entry[4]
            candidate_ip_str = str(sockaddr[0])
            try:
                parsed_ip = ipaddress.ip_address(candidate_ip_str)
                validate_destination_ip(parsed_ip, is_declared_local=self.is_declared_local)
                valid_candidates.append(candidate_ip_str)
            except ValueError as exc:
                raise httpcore.ConnectError(
                    f"SSRF Protection: Connection to '{host}' blocked by security policy: {exc}"
                ) from exc

        if not valid_candidates:
            raise httpcore.ConnectError(
                f"SSRF Protection: No valid IP candidates for '{host}'."
            )

        # Connect directly to the validated IP literal string to avoid any libc getaddrinfo TOCTOU
        last_exc: Optional[Exception] = None
        for target_ip in valid_candidates:
            try:
                return super().connect_tcp(
                    host=target_ip,
                    port=port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:
                last_exc = exc
                continue

        if last_exc:
            raise last_exc
        raise httpcore.ConnectError(f"Failed to connect to any resolved IP for '{host}'.")


class SSRFProtectingTransport(httpx.HTTPTransport):
    """
    HTTP transport wrapping SSRFProtectingBackend with environment trust disabled.
    """

    def __init__(self, is_declared_local: bool = True, **kwargs: Any):
        kwargs["proxy"] = None
        kwargs["trust_env"] = False
        super().__init__(**kwargs)
        self.is_declared_local = is_declared_local
        ssl_ctx = getattr(self._pool, "_ssl_context", None)
        self._pool = httpcore.ConnectionPool(
            ssl_context=ssl_ctx,
            max_connections=getattr(self._pool, "_max_connections", 10),
            max_keepalive_connections=getattr(self._pool, "_max_keepalive_connections", None),
            keepalive_expiry=getattr(self._pool, "_keepalive_expiry", None),
            http1=True,
            http2=False,
            retries=getattr(self._pool, "_retries", 0),
            network_backend=SSRFProtectingBackend(is_declared_local=is_declared_local),
        )


class OllamaAdapter(ProviderInterface):
    """
    Adapter for Ollama local runtime executing on macOS, Linux, and Windows.
    Secured against SSRF and DNS rebinding via connection-time IP validation and socket pinning.
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

        cleaned_host = raw_host.strip("[]")
        self.is_declared_local = (cleaned_host in ALLOWED_LOCAL_HOSTNAMES)

        # Preflight blocklist check
        if cleaned_host in BLOCKED_METADATA_HOSTNAMES:
            raise ValueError(
                f"Access to cloud metadata endpoints ({raw_host}) is forbidden (BRAH-SEC-005 SSRF protection)."
            )

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        ip_candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []

        # 1. Check for integer, hex, or octal IP representations
        try:
            int_val = int(raw_host, 0)
            if 0 <= int_val <= 0xFFFFFFFF:
                ip_candidates.append(ipaddress.IPv4Address(int_val))
        except (ValueError, TypeError):
            pass

        # 2. Check for direct IPv4 or IPv6 literal
        try:
            direct_ip = ipaddress.ip_address(cleaned_host)
            ip_candidates.append(direct_ip)
        except ValueError:
            pass

        # 3. DNS resolution via socket.getaddrinfo to preflight-resolve hostnames
        try:
            addr_info = socket.getaddrinfo(cleaned_host, port, proto=socket.IPPROTO_TCP)
            for entry in addr_info:
                sockaddr = entry[4]
                candidate_str = str(sockaddr[0])
                try:
                    resolved_ip = ipaddress.ip_address(candidate_str)
                    ip_candidates.append(resolved_ip)
                except ValueError:
                    pass
        except (socket.gaierror, OSError):
            pass

        # 4. Preflight Network Policy Evaluation
        for ip in ip_candidates:
            validate_destination_ip(ip, is_declared_local=self.is_declared_local)

        self.endpoint = raw_endpoint
        self.timeout = timeout

    @property
    def provider_type(self) -> str:
        return "ollama"

    def _get_client(self, timeout: float) -> httpx.Client:
        transport = SSRFProtectingTransport(is_declared_local=self.is_declared_local)
        return httpx.Client(
            transport=transport,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        )

    def _handle_http_error(self, exc: Exception) -> None:
        """Map local daemon errors and SSRF security blocks to normalized domain exceptions."""
        exc_str = str(exc)
        if "SSRF Protection" in exc_str or "BRAH-SEC-005" in exc_str or "rebinding" in exc_str.lower():
            raise InvalidRequestError(
                f"SSRF Protection: Outbound connection blocked: {exc}",
                provider="ollama",
                status_code=400,
            )
        if isinstance(exc, (httpx.ConnectError, httpx.NetworkError, httpcore.ConnectError)):
            raise ProviderUnavailableError(
                f"Ollama local runtime is not running at {self.endpoint}. "
                "Start Ollama via the application or run 'ollama serve'.",
                provider="ollama",
            )
        if isinstance(exc, (httpx.TimeoutException, httpx.ReadTimeout, httpcore.TimeoutException)):
            raise TimeoutError(
                f"Ollama request timed out after {self.timeout}s.",
                provider="ollama",
            )
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            detail = exc.response.text
            if code == 404:
                raise InvalidRequestError(
                    "Model not found in local Ollama repository. Run 'ollama pull <model>' first.",
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
            with self._get_client(timeout=self.timeout) as client:
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
            with self._get_client(timeout=10.0) as client:
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
            with self._get_client(timeout=5.0) as client:
                res = client.get(url)
                res.raise_for_status()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return HealthStatus(
                status="HEALTHY",
                latency_ms=round(elapsed_ms, 2),
                details=f"Ollama local runtime reachable at {self.endpoint}",
            )
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return HealthStatus(
                status="UNREACHABLE",
                latency_ms=round(elapsed_ms, 2),
                details="Ollama is not running locally. Start it with 'ollama serve'.",
            )
