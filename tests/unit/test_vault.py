"""
Unit tests for Vault abstractions: InMemoryVault and MacOSKeychainVault.
"""

from unittest.mock import MagicMock, patch
import pytest

from brahmastra.infrastructure.vault.memory_vault import InMemoryVault
from brahmastra.infrastructure.vault.macos_keychain import MacOSKeychainVault
from brahmastra.infrastructure.vault.factory import get_vault


def test_in_memory_vault_lifecycle():
    """Verify storing, retrieving, checking, and deleting secrets in memory."""
    vault = InMemoryVault()

    # Initially empty
    assert vault.has_secret("brahmastra", "acc1") is False
    assert vault.get_secret("brahmastra", "acc1") is None

    # Store
    ref = vault.store_secret("brahmastra", "acc1", "sk-secret-123")
    assert ref == "vault:brahmastra:acc1"
    assert vault.has_secret("brahmastra", "acc1") is True
    assert vault.get_secret("brahmastra", "acc1") == "sk-secret-123"

    # Update
    vault.store_secret("brahmastra", "acc1", "sk-secret-456")
    assert vault.get_secret("brahmastra", "acc1") == "sk-secret-456"

    # Delete
    deleted = vault.delete_secret("brahmastra", "acc1")
    assert deleted is True
    assert vault.has_secret("brahmastra", "acc1") is False
    assert vault.get_secret("brahmastra", "acc1") is None

    # Deleting absent key returns False
    assert vault.delete_secret("brahmastra", "acc1") is False


def test_in_memory_vault_rejects_empty_secret():
    """Verify empty secret string is rejected."""
    vault = InMemoryVault()
    with pytest.raises(ValueError, match="cannot be empty"):
        vault.store_secret("brahmastra", "acc1", "")


@patch("subprocess.run")
def test_macos_keychain_vault_store(mock_run):
    """Verify macOS Keychain store command uses -U flag."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    vault = MacOSKeychainVault(executable_path="/usr/bin/security", use_native=False)
    ref = vault.store_secret("brahmastra-service", "acc-openrouter", "secret-token")
    assert ref == "vault:brahmastra-service:acc-openrouter"

    mock_run.assert_called_once_with(
        ["/usr/bin/security", "add-generic-password", "-a", "acc-openrouter", "-s", "brahmastra-service", "-w", "secret-token", "-U"],
        capture_output=True,
        text=True,
    )


@patch("subprocess.run")
def test_macos_keychain_vault_store_failure(mock_run):
    """Verify macOS Keychain store failure raises RuntimeError."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Access denied")

    vault = MacOSKeychainVault(use_native=False)
    with pytest.raises(RuntimeError, match="Failed to store secret"):
        vault.store_secret("service", "acc", "token")


@patch("subprocess.run")
def test_macos_keychain_vault_get(mock_run):
    """Verify macOS Keychain get command strips trailing newline."""
    mock_run.return_value = MagicMock(returncode=0, stdout="my-secret-key\n", stderr="")

    vault = MacOSKeychainVault(use_native=False)
    secret = vault.get_secret("service", "acc")
    assert secret == "my-secret-key"

    mock_run.assert_called_once_with(
        ["/usr/bin/security", "find-generic-password", "-a", "acc", "-s", "service", "-w"],
        capture_output=True,
        text=True,
    )


@patch("subprocess.run")
def test_macos_keychain_vault_get_not_found(mock_run):
    """Verify get returns None when key is not found in keychain."""
    mock_run.return_value = MagicMock(returncode=44, stdout="", stderr="Item not found")

    vault = MacOSKeychainVault(use_native=False)
    secret = vault.get_secret("service", "nonexistent")
    assert secret is None


@patch("subprocess.run")
def test_macos_keychain_vault_delete(mock_run):
    """Verify delete executes delete-generic-password."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    vault = MacOSKeychainVault(use_native=False)
    res = vault.delete_secret("service", "acc")
    assert res is True


@patch("subprocess.run")
def test_macos_keychain_vault_has_secret(mock_run):
    """Verify has_secret does not use -w flag to protect secrets."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    vault = MacOSKeychainVault(use_native=False)
    res = vault.has_secret("service", "acc")
    assert res is True

    # Assert -w flag was NOT used
    called_cmd = mock_run.call_args[0][0]
    assert "-w" not in called_cmd


def test_vault_factory(monkeypatch):
    """Verify factory returns appropriate vault implementation."""
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")
    vault = get_vault()
    assert isinstance(vault, InMemoryVault)

    vault_explicit = get_vault(vault_type="keychain")
    assert isinstance(vault_explicit, MacOSKeychainVault)
