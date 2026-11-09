"""
Vault factory resolving vault implementation based on OS and environment.
"""

import os
import platform
from typing import Optional
from brahmastra.domain.vault.interface import VaultInterface
from brahmastra.infrastructure.vault.macos_keychain import MacOSKeychainVault
from brahmastra.infrastructure.vault.memory_vault import InMemoryVault

_default_vault: Optional[VaultInterface] = None
_default_memory_vault: Optional[InMemoryVault] = None


def get_vault(vault_type: Optional[str] = None) -> VaultInterface:
    """
    Get the configured vault backend.
    Checks BRAHMASTRA_VAULT environment variable:
      - 'memory': InMemoryVault (ideal for tests / CI)
      - 'keychain': MacOSKeychainVault
    Defaults to MacOSKeychainVault on Darwin (macOS), or InMemoryVault if outside macOS.
    """
    global _default_vault, _default_memory_vault

    selected = vault_type or os.environ.get("BRAHMASTRA_VAULT")
    if selected == "memory":
        if _default_memory_vault is None:
            _default_memory_vault = InMemoryVault()
        return _default_memory_vault

    if selected == "keychain":
        if _default_vault is None:
            _default_vault = MacOSKeychainVault()
        return _default_vault

    if platform.system() == "Darwin":
        if _default_vault is None:
            _default_vault = MacOSKeychainVault()
        return _default_vault

    # Non-macOS fallback default
    if _default_memory_vault is None:
        _default_memory_vault = InMemoryVault()
    return _default_memory_vault
