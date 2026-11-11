"""
Security tests for macOS Keychain Vault native C-level implementation (BRAH-SEC-002).
Verifies that secrets are stored directly via Security.framework in-memory APIs
and NEVER passed as command-line arguments to subprocesses.
"""
import sys
from unittest.mock import patch
import pytest

from brahmastra.infrastructure.vault.macos_keychain import MacOSKeychainVault


@pytest.mark.skipif(sys.platform != "darwin", reason="Native Keychain tests require macOS")
@patch("subprocess.run")
def test_native_keychain_zero_subprocess_argv_exposure(mock_subprocess):
    """Verify storing secret via native Security.framework invokes NO subprocesses with argv."""
    vault = MacOSKeychainVault(use_native=True)

    service = "brahmastra_sec_test"
    account = "sec_account"
    secret = "sk-test-secret-never-in-argv-999"

    try:
        # Store secret
        ref = vault.store_secret(service, account, secret)
        assert ref == f"vault:{service}:{account}"

        # Subprocess MUST NEVER be called
        mock_subprocess.assert_not_called()

        # Clear process cache to force fetching from Keychain
        vault._cache.clear()

        # Retrieve secret from Keychain
        retrieved = vault.get_secret(service, account)
        assert retrieved == secret
        mock_subprocess.assert_not_called()

        # Update / Rotate secret
        new_secret = "sk-test-rotated-secret-888"
        vault.store_secret(service, account, new_secret)
        vault._cache.clear()

        retrieved_updated = vault.get_secret(service, account)
        assert retrieved_updated == new_secret
        mock_subprocess.assert_not_called()

        # Check has_secret
        vault._cache.clear()
        assert vault.has_secret(service, account) is True
        mock_subprocess.assert_not_called()

    finally:
        # Cleanup
        vault.delete_secret(service, account)
        mock_subprocess.assert_not_called()


@patch("subprocess.run")
def test_keychain_vault_fails_closed_when_native_bindings_unavailable(mock_subprocess):
    """Verify that if native bindings are unavailable, store_secret fails closed rather than leaking in argv."""
    vault = MacOSKeychainVault(use_native=False)
    with pytest.raises(RuntimeError, match="unavailable"):
        vault.store_secret("service", "account", "secret123")

    # Must NOT call subprocess.run with -w secret
    mock_subprocess.assert_not_called()
