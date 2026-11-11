"""
Security tests for Ollama adapter endpoint validation and SSRF prevention (BRAH-SEC-005).
"""
from unittest.mock import patch
import socket
import httpcore
import pytest

from brahmastra.infrastructure.providers.ollama import (
    OllamaAdapter,
    SSRFProtectingBackend,
)
from brahmastra.domain.providers.models import GenerationRequest, ChatMessage
from brahmastra.domain.providers.exceptions import InvalidRequestError


@pytest.mark.parametrize(
    "bad_endpoint",
    [
        "file:///etc/passwd",
        "gopher://127.0.0.1:11434",
        "ftp://example.com/model",
        "javascript:alert(1)",
    ],
)
def test_ollama_invalid_scheme_rejected(bad_endpoint):
    """Verify non-HTTP/HTTPS schemes are blocked with ValueError."""
    with pytest.raises(ValueError, match="Invalid endpoint scheme"):
        OllamaAdapter(endpoint=bad_endpoint)


@pytest.mark.parametrize(
    "metadata_endpoint",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254:80",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://2852039166:80",
        "http://0xa9fea9fe:80",
        "http://[::ffff:169.254.169.254]:80",
        "http://169.254.169.254.nip.io:80",
        "http://[fd00:ec2::254]:80",
        "http://10.0.0.1:80",
        "http://192.168.1.1:80",
        "http://172.16.0.1:80",
    ],
)
def test_ollama_cloud_metadata_endpoint_rejected(metadata_endpoint):
    """Verify cloud metadata and private network destinations are blocked to prevent SSRF."""
    with pytest.raises(ValueError, match="SSRF|metadata|private|forbidden|prohibited"):
        OllamaAdapter(endpoint=metadata_endpoint)


@pytest.mark.parametrize(
    "valid_endpoint",
    [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://[::1]:11434",
    ],
)
def test_ollama_valid_endpoints_accepted(valid_endpoint):
    """Verify legitimate loopback endpoints initialize properly."""
    adapter = OllamaAdapter(endpoint=valid_endpoint)
    assert adapter.endpoint.startswith("http")


def test_dns_rebinding_external_domain_resolving_to_loopback_rejected():
    """Verify that an external domain resolving to 127.0.0.1 is rejected as a DNS rebinding attack."""
    fake_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 11434))
    ]
    with patch("socket.getaddrinfo", return_value=fake_addr_info):
        with pytest.raises(ValueError, match="DNS rebinding attack detected"):
            OllamaAdapter(endpoint="http://rebind.attacker.com:11434")


def test_dns_rebinding_toctou_at_connection_time_blocked():
    """
    Verify TOCTOU protection: initial DNS returns safe IP, but connection-time DNS
    rebinds to cloud metadata or internal loopback. SSRFProtectingBackend MUST block.
    """
    initial_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 11434))
    ]
    # In __init__, resolve to safe IP
    with patch("socket.getaddrinfo", return_value=initial_addr_info):
        adapter = OllamaAdapter(endpoint="http://api.example.com:11434")

    # At request connection time, DNS rebinds to cloud metadata 169.254.169.254
    rebinding_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 11434))
    ]
    backend = SSRFProtectingBackend(is_declared_local=adapter.is_declared_local)
    with patch("socket.getaddrinfo", return_value=rebinding_addr_info):
        with pytest.raises(httpcore.ConnectError, match="SSRF Protection|cloud metadata"):
            backend.connect_tcp("api.example.com", 11434)


def test_dns_rebinding_toctou_handled_in_adapter():
    """Verify that connection-time DNS rebinding aborts request cleanly via InvalidRequestError."""
    initial_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 11434))
    ]
    with patch("socket.getaddrinfo", return_value=initial_addr_info):
        adapter = OllamaAdapter(endpoint="http://api.example.com:11434")

    # Subsequent call rebinds to loopback 127.0.0.1
    rebinding_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 11434))
    ]
    with patch("socket.getaddrinfo", return_value=rebinding_addr_info):
        req = GenerationRequest(
            model="llama3",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        with pytest.raises(InvalidRequestError, match="SSRF Protection|rebinding"):
            adapter.generate(req)


@pytest.mark.parametrize(
    "exotic_ip_endpoint",
    [
        "http://100.100.100.200:80",             # Alibaba Cloud metadata
        "http://100.64.0.1:80",                   # Carrier-Grade NAT (CGNAT)
        "http://[64:ff9b::1]:80",                 # NAT64 well-known prefix
        "http://[2002:a9fe:a9fe::]:80",           # 6to4 pointing to 169.254.169.254
    ],
)
def test_exotic_metadata_and_tunnel_ssrf_blocked(exotic_ip_endpoint):
    """Verify CGNAT, NAT64, and 6to4 tunneling vectors are strictly blocked."""
    with pytest.raises(ValueError, match="SSRF|forbidden|prohibited"):
        OllamaAdapter(endpoint=exotic_ip_endpoint)


def test_http_transport_security_defaults():
    """Verify redirect following and proxy trust are strictly disabled on HTTP client."""
    adapter = OllamaAdapter()
    client = adapter._get_client(timeout=10.0)
    assert client.follow_redirects is False
    assert client._transport.is_declared_local is True
