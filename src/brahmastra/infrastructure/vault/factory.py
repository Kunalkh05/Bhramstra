"""
Vault factory resolving vault implementation based on OS and environment.
Cross-platform support for macOS, Linux, and Windows.
"""

import os
import platform
from typing import Optional
from brahmastra.domain.vault.interface import VaultInterface
from brahmastra.infrastructure.vault.macos_keychain import MacOSKeychainVault
from brahmastra.infrastructure.vault.windows_cred import WindowsCredentialVault
from brahmastra.infrastructure.vault.linux_secret import LinuxSecretVault
from brahmastra.infrastructure.vault.memory_vault import InMemoryVault

_default_vault: Optional[VaultInterface] = None
_default_memory_vault: Optional[InMemoryVault] = None


def get_vault(vault_type: Optional[str] = None) -> VaultInterface:
    """
    Get the configured vault backend.
    Checks BRAHMASTRA_VAULT environment variable:
      - 'memory': InMemoryVault (ideal for tests / CI)
      - 'keychain': MacOSKeychainVault
      - 'wincred': WindowsCredentialVault
      - 'linuxsecret': LinuxSecretVault
    Platform defaults:
      - Darwin (macOS): MacOSKeychainVault (native C bindings to Security.framework)
      - Windows: WindowsCredentialVault (native C bindings to Advapi32.dll)
      - Linux / POSIX: LinuxSecretVault (authenticated encrypted persistent storage)
    """
    global _default_vault, _default_memory_vault

    selected = vault_type or os.environ.get("BRAHMASTRA_VAULT")
    if selected == "memory":
        if _default_memory_vault is None:
            _default_memory_vault = InMemoryVault()
        return _default_memory_vault

    if selected == "keychain":
        if _default_vault is None or not isinstance(_default_vault, MacOSKeychainVault):
            _default_vault = MacOSKeychainVault()
        return _default_vault

    if selected == "wincred":
        if _default_vault is None or not isinstance(_default_vault, WindowsCredentialVault):
            _default_vault = WindowsCredentialVault()
        return _default_vault

    if selected == "linuxsecret":
        if _default_vault is None or not isinstance(_default_vault, LinuxSecretVault):
            _default_vault = LinuxSecretVault()
        return _default_vault

    sys_name = platform.system()
    if sys_name == "Darwin":
        if _default_vault is None or not isinstance(_default_vault, MacOSKeychainVault):
            _default_vault = MacOSKeychainVault()
        return _default_vault
    elif sys_name == "Windows":
        if _default_vault is None or not isinstance(_default_vault, WindowsCredentialVault):
            _default_vault = WindowsCredentialVault()
        return _default_vault
    elif sys_name == "Linux":
        if _default_vault is None or not isinstance(_default_vault, LinuxSecretVault):
            _default_vault = LinuxSecretVault()
        return _default_vault

    # Fallback to LinuxSecretVault for any other POSIX/Unix environments
    if _default_vault is None:
        _default_vault = LinuxSecretVault()
    return _default_vault
