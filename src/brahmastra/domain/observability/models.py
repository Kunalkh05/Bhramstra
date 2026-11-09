"""
Domain models for request-level usage records and accounting.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class UsageRecordCreate(BaseModel):
    """Schema to record request usage."""
    org_name: str
    account_name: str
    model_id: str
    prompt_tokens: int = Field(0, ge=0)
    completion_tokens: int = Field(0, ge=0)
    cost_micro_usd: int = Field(0, ge=0, description="Cost in micro-USD (1 USD = 1,000,000 micro-USD)")
    latency_ms: Optional[float] = Field(None, ge=0.0)


class UsageRecord(BaseModel):
    """Domain model representing a single attribution record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_name: str
    account_name: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_micro_usd: int
    latency_ms: Optional[float] = None
    timestamp: datetime

    @property
    def cost_usd(self) -> float:
        """Formatted cost in USD."""
        return self.cost_micro_usd / 1_000_000.0


class ModelUsageBreakdown(BaseModel):
    """Token and cost summary for a model."""
    model_id: str
    requests: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


class OrgUsageBreakdown(BaseModel):
    """Token and cost summary for an organization."""
    org_name: str
    requests: int
    total_tokens: int
    cost_usd: float


class UsageSummary(BaseModel):
    """Aggregated usage metrics."""
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: float
    models: List[ModelUsageBreakdown] = []
    orgs: List[OrgUsageBreakdown] = []
