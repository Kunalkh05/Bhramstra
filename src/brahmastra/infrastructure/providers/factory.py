"""
Provider adapter factory.
"""

from typing import Optional
from brahmastra.domain.providers.interface import ProviderInterface
from brahmastra.domain.providers.exceptions import UnknownProviderError
from brahmastra.infrastructure.providers.openrouter import OpenRouterAdapter
from brahmastra.infrastructure.providers.ollama import OllamaAdapter


def get_provider_adapter(
    provider_type: str,
    endpoint: Optional[str] = None,
) -> ProviderInterface:
    """
    Instantiate and return the appropriate ProviderInterface implementation.
    """
    normalized = provider_type.strip().lower()

    if normalized == "openrouter":
        return OpenRouterAdapter(endpoint=endpoint)

    if normalized == "ollama":
        return OllamaAdapter(endpoint=endpoint)

    raise UnknownProviderError(
        f"Provider type '{provider_type}' is not currently supported. "
        "Supported providers are 'openrouter' and 'ollama'.",
        provider=provider_type,
    )
