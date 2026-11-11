"""
Platform vault tests for Windows Credential Manager and Linux Secret Vault.
"""
import platform
import sys
from unittest.mock import MagicMock
import pytest

from brahmastra.domain.vault.interface import VaultInterface
from brahmastra.infrastructure.vault.windows_cred import WindowsCredentialVault
from brahmastra.infrastructure.vault.linux_secret import LinuxSecretVault
from brahmastra.infrastructure.vault.factory import get_vault
from brahmastra.infrastructure.vault.memory_vault import InMemoryVault
from brahmastra.infrastructure.vault.macos_keychain import MacOSKeychainVault


def test_windows_cred_vault_interface_compliance():
    """Verify WindowsCredentialVault implements VaultInterface."""
    vault = WindowsCredentialVault(use_native=False)
    assert isinstance(vault, VaultInterface)


def test_windows_cred_vault_rejects_empty_secret():
    """Verify empty secret string is rejected with ValueError."""
    vault = WindowsCredentialVault(use_native=False)
    with pytest.raises(ValueError, match="cannot be empty"):
        vault.store_secret("service", "acc", "")


def test_windows_cred_vault_fails_closed_when_native_unavailable():
    """Verify WindowsCredentialVault fails closed when Advapi32 is unavailable."""
    vault = WindowsCredentialVault(use_native=False)
    with pytest.raises(RuntimeError, match="Advapi32|Windows"):
        vault.store_secret("service", "acc", "supersecret")


def test_windows_cred_vault_mocked_lifecycle():
    """Verify WindowsCredentialVault lifecycle using mocked Advapi32 bindings."""
    vault = WindowsCredentialVault(use_native=False)

    fake_advapi = MagicMock()
    # CredWriteW succeeds (returns nonzero)
    fake_advapi.CredWriteW.return_value = 1
    # CredDeleteW succeeds
    fake_advapi.CredDeleteW.return_value = 1
    # CredFree succeeds
    fake_advapi.CredFree.return_value = None

    vault._advapi = fake_advapi
    vault.use_native = True

    # Store
    ref = vault.store_secret("test-svc", "test-acc", "win-secret-123")
    assert "test-svc" in ref
    assert vault.get_secret("test-svc", "test-acc") == "win-secret-123"
    assert vault.has_secret("test-svc", "test-acc") is True

    # Delete
    deleted = vault.delete_secret("test-svc", "test-acc")
    assert deleted is True
    assert vault.has_secret("test-svc", "test-acc") is False
    assert vault.get_secret("test-svc", "test-acc") is None


def test_linux_secret_vault_secret_service_lifecycle():
    """Verify LinuxSecretVault lifecycle using injected Secret Service backend."""
    fake_backend = MagicMock()
    store = {}
    fake_backend.set_password.side_effect = lambda s, u, p: store.update({(s, u): p})
    fake_backend.get_password.side_effect = lambda s, u: store.get((s, u))
    fake_backend.delete_password.side_effect = lambda s, u: store.pop((s, u), None)

    vault = LinuxSecretVault(backend=fake_backend)

    # Initial state
    assert vault.has_secret("linux-svc", "acc1") is False
    assert vault.get_secret("linux-svc", "acc1") is None

    # Store
    ref = vault.store_secret("linux-svc", "acc1", "linux-secret-xyz")
    assert "linux-svc" in ref
    assert vault.has_secret("linux-svc", "acc1") is True
    assert vault.get_secret("linux-svc", "acc1") == "linux-secret-xyz"
    assert store[("brahmastra:linux-svc", "acc1")] == "linux-secret-xyz"

    # Delete
    deleted = vault.delete_secret("linux-svc", "acc1")
    assert deleted is True
    assert vault.has_secret("linux-svc", "acc1") is False
    assert vault.get_secret("linux-svc", "acc1") is None


def test_linux_secret_vault_unavailable_fails_closed():
    """Verify LinuxSecretVault fails closed when backend is unavailable or fail backend."""
    class FailBackend:
        pass

    vault = LinuxSecretVault(backend=FailBackend())
    with pytest.raises(RuntimeError, match="unavailable|Secret Service"):
        vault.store_secret("svc", "acc", "secret-data")


def test_vault_factory_cross_platform_dispatch(monkeypatch):
    """Verify factory dispatches to platform-native vaults."""
    # Test memory override
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")
    assert isinstance(get_vault(), InMemoryVault)
    monkeypatch.delenv("BRAHMASTRA_VAULT", raising=False)

    # Test Darwin dispatch
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    assert isinstance(get_vault(vault_type="keychain"), MacOSKeychainVault)

    # Test Windows dispatch
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    assert isinstance(get_vault(vault_type="wincred"), WindowsCredentialVault)

    # Test Linux dispatch
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert isinstance(get_vault(vault_type="linuxsecret"), LinuxSecretVault)


@pytest.mark.skipif(sys.platform != "win32", reason="Requires native Windows")
def test_live_windows_cred_lifecycle():
    """Verify live Windows Credential Manager store, retrieve, and delete on Windows."""
    vault = WindowsCredentialVault(use_native=True)
    if not vault.use_native:
        pytest.skip("Native Advapi32 bindings unavailable")

    service = "brahmastra_live_test_svc"
    account = "live_test_user"
    secret = "live_test_secret_win32"

    try:
        # Pre-cleanup
        vault.delete_secret(service, account)

        # Store
        ref = vault.store_secret(service, account, secret)
        assert service in ref

        # Query & Retrieve
        assert vault.has_secret(service, account) is True
        assert vault.get_secret(service, account) == secret

        # Delete
        assert vault.delete_secret(service, account) is True
        assert vault.has_secret(service, account) is False
        assert vault.get_secret(service, account) is None
    finally:
        vault.delete_secret(service, account)


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS")
def test_live_macos_keychain_lifecycle():
    """Verify live macOS Keychain store, retrieve, and delete on macOS."""
    vault = MacOSKeychainVault(use_native=True)
    if not vault.use_native:
        pytest.skip("Native Security.framework bindings unavailable")

    service = "brahmastra_live_test_svc"
    account = "live_test_user"
    secret = "live_test_secret_darwin"

    try:
        # Pre-cleanup
        vault.delete_secret(service, account)

        # Store
        ref = vault.store_secret(service, account, secret)
        assert service in ref

        # Query & Retrieve
        assert vault.has_secret(service, account) is True
        assert vault.get_secret(service, account) == secret

        # Delete
        assert vault.delete_secret(service, account) is True
        assert vault.has_secret(service, account) is False
        assert vault.get_secret(service, account) is None
    finally:
        vault.delete_secret(service, account)

