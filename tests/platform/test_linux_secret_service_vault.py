"""
Unit and integration tests for Linux Secret Service vault (org.freedesktop.secrets).
Distinguishes hermetic mocked unit tests from live Linux integration tests.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from keyring.errors import KeyringError, NoKeyringError

from brahmastra.domain.vault.interface import VaultInterface
from brahmastra.infrastructure.vault.linux_secret import LinuxSecretVault, _is_backend_usable


class FakeSecretServiceBackend:
    """Mock of keyring SecretService KeyringBackend."""

    def __init__(self, should_fail: bool = False, auth_fail: bool = False):
        self.should_fail = should_fail
        self.auth_fail = auth_fail
        self._store = {}

    def get_password(self, service, username):
        if self.auth_fail:
            raise KeyringError("Authentication to Secret Service failed: Access denied")
        if self.should_fail:
            raise NoKeyringError("No Secret Service daemon running on D-Bus")
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        if self.auth_fail:
            raise KeyringError("Authentication to Secret Service failed: Access denied")
        if self.should_fail:
            raise NoKeyringError("No Secret Service daemon running on D-Bus")
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        if self.auth_fail:
            raise KeyringError("Authentication to Secret Service failed: Access denied")
        if self.should_fail:
            raise NoKeyringError("No Secret Service daemon running on D-Bus")
        if (service, username) in self._store:
            del self._store[(service, username)]
        else:
            raise KeyringError("Password not found")


class FailKeyringBackend:
    """Simulates keyring.backends.fail.Keyring."""
    pass


class PlaintextKeyringBackend:
    """Simulates insecure plaintext file keyring."""
    pass


class FileKeyringBackend:
    """Simulates local file keyring."""
    pass


# ---------------------------------------------------------------------------
# Mocked Unit Tests (Platform-Agnostic)
# ---------------------------------------------------------------------------


def test_linux_vault_implements_interface():
    """Verify LinuxSecretVault implements VaultInterface."""
    backend = FakeSecretServiceBackend()
    vault = LinuxSecretVault(backend=backend)
    assert isinstance(vault, VaultInterface)


def test_linux_vault_rejects_empty_secret():
    """Verify storing an empty secret raises ValueError."""
    backend = FakeSecretServiceBackend()
    vault = LinuxSecretVault(backend=backend)
    with pytest.raises(ValueError, match="cannot be empty"):
        vault.store_secret("service", "acc", "")


def test_secret_service_available_lifecycle():
    """Verify store, retrieve, check, and delete operations with active Secret Service."""
    backend = FakeSecretServiceBackend()
    vault = LinuxSecretVault(backend=backend)

    assert vault.has_secret("brahmastra-ai", "user1") is False
    assert vault.get_secret("brahmastra-ai", "user1") is None

    # Store
    ref = vault.store_secret("brahmastra-ai", "user1", "sk-secret-token-123")
    assert ref == "vault:brahmastra-ai:user1"
    assert vault.has_secret("brahmastra-ai", "user1") is True
    assert vault.get_secret("brahmastra-ai", "user1") == "sk-secret-token-123"

    # Backend verification
    assert backend.get_password("brahmastra:brahmastra-ai", "user1") == "sk-secret-token-123"

    # Delete
    deleted = vault.delete_secret("brahmastra-ai", "user1")
    assert deleted is True
    assert vault.has_secret("brahmastra-ai", "user1") is False
    assert vault.get_secret("brahmastra-ai", "user1") is None


def test_secret_service_unavailable_fails_closed():
    """Verify LinuxSecretVault fails closed when Secret Service is unavailable."""
    backend = FakeSecretServiceBackend(should_fail=True)
    vault = LinuxSecretVault(backend=backend)

    with pytest.raises(RuntimeError, match="unavailable|Secret Service"):
        vault.store_secret("brahmastra-ai", "user1", "mysecret")

    with pytest.raises(RuntimeError, match="unavailable|Secret Service"):
        vault.get_secret("brahmastra-ai", "user1")


def test_secret_service_fail_backend_rejected():
    """Verify fail/null keyring backends fail closed with RuntimeError."""
    backend = FailKeyringBackend()
    vault = LinuxSecretVault(backend=backend)

    with pytest.raises(RuntimeError, match="unavailable|Secret Service"):
        vault.store_secret("brahmastra-ai", "user1", "mysecret")


def test_insecure_plaintext_and_file_backends_rejected():
    """Verify plaintext and local file backends are strictly rejected."""
    for bad_backend in [PlaintextKeyringBackend(), FileKeyringBackend()]:
        vault = LinuxSecretVault(backend=bad_backend)
        with pytest.raises(RuntimeError, match="unavailable|Secret Service|Insecure plaintext"):
            vault.store_secret("brahmastra-ai", "user1", "mysecret")


def test_missing_secretstorage_fails_closed_safely():
    """Verify keyring SecretService without SecretStorage fails closed with clean diagnostic error."""
    class UnusableSecretService:
        __module__ = "keyring.backends.SecretService"

        @property
        def priority(self):
            raise RuntimeError("SecretStorage required")

    backend = UnusableSecretService()
    assert _is_backend_usable(backend) is False

    vault = LinuxSecretVault(backend=backend)
    with pytest.raises(RuntimeError, match="Linux Secret Service is unavailable"):
        vault.store_secret("brahmastra-ai", "user1", "mysecret")


def test_backend_priority_getter_exception_fails_closed():
    """Verify dynamic exceptions in backend.priority property fail closed safely."""
    class RaisingPriorityBackend:
        __module__ = "keyring.backends.SecretService"

        @property
        def priority(self):
            raise RuntimeError("D-Bus session bus disconnected")

    backend = RaisingPriorityBackend()
    assert _is_backend_usable(backend) is False

    vault = LinuxSecretVault(backend=backend)
    with pytest.raises(RuntimeError, match="Linux Secret Service is unavailable"):
        vault.store_secret("brahmastra-ai", "user1", "mysecret")


def test_negative_priority_backend_rejected():
    """Verify backends declaring negative priority are rejected."""
    class NegativePriorityBackend:
        __module__ = "keyring.backends.SecretService"
        priority = -1

    backend = NegativePriorityBackend()
    assert _is_backend_usable(backend) is False

    vault = LinuxSecretVault(backend=backend)
    with pytest.raises(RuntimeError, match="Linux Secret Service is unavailable"):
        vault.store_secret("brahmastra-ai", "user1", "mysecret")


def test_approved_backend_selection_by_module_and_name():
    """Verify approved SecretService and KWallet backends are accepted when priority is valid."""
    class ValidSecretService:
        __module__ = "keyring.backends.SecretService"
        priority = 5

    class ValidKWallet:
        __module__ = "keyring.backends.KWallet"
        priority = 5

    assert _is_backend_usable(ValidSecretService()) is True
    assert _is_backend_usable(ValidKWallet()) is True


def test_disallowed_backend_by_module_path_rejected():
    """Verify backends with disallowed modules are rejected even if class name is generic."""
    class GenericKeyring:
        __module__ = "keyring.backends.plain"
        priority = 1

    assert _is_backend_usable(GenericKeyring()) is False


def test_unknown_backend_rejected():
    """Verify unrecognized third-party backends fail closed."""
    class CustomStorageBackend:
        __module__ = "untrusted_third_party.custom_keyring"
        priority = 10

    assert _is_backend_usable(CustomStorageBackend()) is False


def test_secret_service_backend_auth_error_fails_closed():
    """Verify backend authentication / access denied errors raise RuntimeError."""
    backend = FakeSecretServiceBackend(auth_fail=True)
    vault = LinuxSecretVault(backend=backend)

    with pytest.raises(RuntimeError, match="Secret Service|Access denied"):
        vault.store_secret("brahmastra-ai", "user1", "mysecret")


def test_secret_service_malformed_response_handled():
    """Verify malformed backend responses are handled safely without crashing."""
    backend = MagicMock()
    # Backend returns integer instead of string or None
    backend.get_password.return_value = 12345
    vault = LinuxSecretVault(backend=backend)

    res = vault.get_secret("service", "acc")
    assert res == "12345"


def test_credential_isolation_between_accounts_and_services():
    """Verify strict isolation between distinct services and accounts."""
    backend = FakeSecretServiceBackend()
    vault = LinuxSecretVault(backend=backend)

    vault.store_secret("service-alpha", "account-1", "secret-alpha-1")
    vault.store_secret("service-beta", "account-1", "secret-beta-1")
    vault.store_secret("service-alpha", "account-2", "secret-alpha-2")

    assert vault.get_secret("service-alpha", "account-1") == "secret-alpha-1"
    assert vault.get_secret("service-beta", "account-1") == "secret-beta-1"
    assert vault.get_secret("service-alpha", "account-2") == "secret-alpha-2"

    vault.delete_secret("service-alpha", "account-1")
    assert vault.get_secret("service-alpha", "account-1") is None
    assert vault.get_secret("service-beta", "account-1") == "secret-beta-1"
    assert vault.get_secret("service-alpha", "account-2") == "secret-alpha-2"


def test_no_plaintext_credential_persistence(tmp_path, monkeypatch):
    """Verify that credentials are NEVER written to application files or vault.enc."""
    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))
    backend = FakeSecretServiceBackend()
    vault = LinuxSecretVault(backend=backend)

    secret_val = "SUPER-SECRET-PLAINTEXT-999"
    vault.store_secret("openrouter", "acc-prod", secret_val)

    # Inspect all files created in storage dir (portable os.walk for Python 3.10+)
    for root, _, files in os.walk(tmp_path):
        for file in files:
            file_path = Path(root) / file
            assert secret_val.encode() not in file_path.read_bytes(), f"Plaintext secret found in {file_path}"

    # Verify vault.enc is NOT created
    assert not (tmp_path / "vault.enc").exists()


def test_no_insecure_fallback_on_failure():
    """Verify that no insecure plaintext file or memory fallback occurs when Secret Service fails."""
    backend = FakeSecretServiceBackend(should_fail=True)
    vault = LinuxSecretVault(backend=backend)

    with pytest.raises(RuntimeError):
        vault.store_secret("service", "acc", "token123")

    # Ensure secret was NOT stored in memory cache as a fallback
    assert vault.has_secret("service", "acc") is False


# ---------------------------------------------------------------------------
# Actual Linux Host Integration Test (Gated on sys.platform == "linux")
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "linux", reason="Requires real Linux environment with system Secret Service daemon")
def test_live_linux_secret_service_integration():
    """
    Integration test executed only on actual Linux hosts.
    Verifies communication with the real system Secret Service daemon over D-Bus.
    Must fail if Secret Service daemon is unavailable.
    """
    vault = LinuxSecretVault()
    # Live execution must succeed without catching or masking errors
    ref = vault.store_secret("brahmastra-test", "test-user", "live-linux-secret")
    assert ref.startswith("vault:")
    assert vault.get_secret("brahmastra-test", "test-user") == "live-linux-secret"
    deleted = vault.delete_secret("brahmastra-test", "test-user")
    assert deleted is True
    assert vault.get_secret("brahmastra-test", "test-user") is None
