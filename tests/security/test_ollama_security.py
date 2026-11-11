"""
Security tests for Ollama adapter endpoint validation and SSRF prevention (BRAH-SEC-005).
"""
import pytest

from brahmastra.infrastructure.providers.ollama import OllamaAdapter


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
