"""
Normalized provider error taxonomy for BRAHMASTRA AI.
"""


class ProviderError(Exception):
    """Base exception for all provider operations."""
    def __init__(self, message: str, provider: str = "", status_code: int = 0):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class AuthenticationError(ProviderError):
    """Raised on invalid credentials, expired keys, or unauthorized access (HTTP 401/403)."""
    pass


class RateLimitError(ProviderError):
    """Raised when provider rate limit or quota is exceeded (HTTP 429)."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when the provider endpoint is down, unreachable, or throwing 5xx errors."""
    pass


class TimeoutError(ProviderError):
    """Raised when network socket or generation request times out."""
    pass


class InvalidRequestError(ProviderError):
    """Raised when request payload or parameters are invalid (HTTP 400)."""
    pass


class UnsupportedCapabilityError(ProviderError):
    """Raised when a requested capability is not supported by the model or provider."""
    pass


class UnknownProviderError(ProviderError):
    """Raised when provider type is unrecognized."""
    pass
