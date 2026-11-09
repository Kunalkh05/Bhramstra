"""
Domain models for Explainable Routing policies, constraints, and decisions.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from brahmastra.domain.providers.models import ModelCapability


class RoutingPreference(str, Enum):
    LOCAL_FIRST = "LOCAL_FIRST"
    CLOUD_FIRST = "CLOUD_FIRST"
    LOWEST_COST = "LOWEST_COST"
    BALANCED = "BALANCED"


class RoutingConstraints(BaseModel):
    """Hard constraints that a candidate model/account MUST satisfy."""
    require_local: bool = False
    require_capabilities: List[ModelCapability] = []
    min_context_window: int = Field(0, ge=0)
    allowed_providers: Optional[List[str]] = None
    blocked_models: List[str] = []


class CandidateEvaluation(BaseModel):
    """Detailed evaluation log for an individual candidate model."""
    model_id: str
    account_name: str
    provider: str
    is_eligible: bool
    disqualification_reason: Optional[str] = None
    score: float = 0.0


class RouteDecision(BaseModel):
    """
    Explainable output of the routing engine.
    Explains which model/account was selected and why alternatives were excluded.
    """
    selected_model_id: Optional[str] = None
    selected_account_name: Optional[str] = None
    selected_provider: Optional[str] = None
    explanation: str
    candidates_evaluated: List[CandidateEvaluation] = []
    fallback_chain: List[str] = []
