"""
Normalized Provider Interface contract.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from brahmastra.domain.providers.models import (
    GenerationRequest,
    GenerationResponse,
    ModelInfo,
    HealthStatus,
)


class ProviderInterface(ABC):
    """
    Standard interface contract that all LLM backends must implement.
    The routing engine interacts solely with this interface.
    """

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Normalized provider identifier (e.g. 'openrouter', 'ollama')."""
        pass

    @abstractmethod
    def generate(
        self,
        request: GenerationRequest,
        secret: Optional[str] = None,
    ) -> GenerationResponse:
        """
        Execute text generation against the target model.
        Secret is injected ephemerally by the application use case from the Vault.
        """
        pass

    @abstractmethod
    def list_models(
        self,
        secret: Optional[str] = None,
    ) -> List[ModelInfo]:
        """
        Fetch available models and capability metadata from the provider.
        """
        pass

    @abstractmethod
    def health_check(
        self,
        secret: Optional[str] = None,
    ) -> HealthStatus:
        """
        Probe endpoint availability and measure round-trip latency.
        """
        pass
