"""
In-memory fake vault implementation for unit testing and CI isolation.
"""

from typing import Dict, Optional, Tuple
from brahmastra.domain.vault.interface import VaultInterface


class InMemoryVault(VaultInterface):
    """
    Ephemerally stores secrets in memory. Never touches OS Keychain or persistent disk.
    Safe for unit and integration testing.
    """

    def __init__(self):
        self._secrets: Dict[Tuple[str, str], str] = {}

    def store_secret(self, service: str, account: str, secret: str) -> str:
        if not secret:
            raise ValueError("Secret cannot be empty.")
        self._secrets[(service, account)] = secret
        return f"vault:{service}:{account}"

    def get_secret(self, service: str, account: str) -> Optional[str]:
        return self._secrets.get((service, account))

    def delete_secret(self, service: str, account: str) -> bool:
        key = (service, account)
        if key in self._secrets:
            del self._secrets[key]
            return True
        return False

    def has_secret(self, service: str, account: str) -> bool:
        return (service, account) in self._secrets

    def clear(self) -> None:
        """Helper to reset all secrets between tests."""
        self._secrets.clear()
