"""
Domain models for normalized provider requests, responses, models, and health checks.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ModelCapability(str, Enum):
    CHAT = "chat"
    STREAMING = "streaming"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    JSON_OUTPUT = "json_output"


class ChatMessage(BaseModel):
    """Normalized chat message."""
    role: str = Field(..., description="Role: 'system', 'user', or 'assistant'")
    content: str = Field(..., description="Message text content")


class GenerationRequest(BaseModel):
    """Normalized generation request independent of provider wire protocols."""
    model: str = Field(..., description="Provider model identifier (e.g. 'anthropic/claude-3.5-sonnet', 'llama3')")
    messages: List[ChatMessage] = Field(..., min_length=1)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    stream: bool = False


class GenerationUsage(BaseModel):
    """Normalized token accounting."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class GenerationResponse(BaseModel):
    """Normalized generation output."""
    content: str
    model: str
    usage: GenerationUsage = Field(default_factory=GenerationUsage)
    finish_reason: Optional[str] = None


class ModelInfo(BaseModel):
    """Normalized model catalog metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    provider: str
    context_window: int = 4096
    capabilities: List[ModelCapability] = []
    is_local: bool = False
    description: Optional[str] = None


class HealthStatus(BaseModel):
    """Diagnostic health check result for a provider."""
    status: str = Field(..., description="'HEALTHY', 'DEGRADED', or 'UNREACHABLE'")
    latency_ms: Optional[float] = None
    details: Optional[str] = None
