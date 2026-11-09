"""
Abstract interface definition for secure secret storage vaults.
"""

from abc import ABC, abstractmethod
from typing import Optional


class VaultInterface(ABC):
    """
    Normalized contract for secure secret storage backends.
    Implementations may be macOS Keychain, In-Memory Fake, or OS-native keyrings.
    """

    @abstractmethod
    def store_secret(self, service: str, account: str, secret: str) -> str:
        """
        Store a secret for the given service and account identifier.
        Returns a non-secret vault reference string (e.g. 'vault:service:account').
        """
        pass

    @abstractmethod
    def get_secret(self, service: str, account: str) -> Optional[str]:
        """
        Retrieve the plaintext secret for the given service and account.
        Returns None if not found.
        """
        pass

    @abstractmethod
    def delete_secret(self, service: str, account: str) -> bool:
        """
        Delete the secret associated with the service and account.
        Returns True if deleted, False if it was not found.
        """
        pass

    @abstractmethod
    def has_secret(self, service: str, account: str) -> bool:
        """
        Check if a secret exists for the given service and account without reading it.
        """
        pass
