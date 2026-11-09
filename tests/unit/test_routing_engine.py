"""
Unit tests for pure domain RoutingEngine and constraint evaluations.
"""

from datetime import datetime, timezone
from brahmastra.domain.providers.models import ModelInfo, ModelCapability
from brahmastra.domain.credentials.models import ProviderAccount
from brahmastra.domain.routing.models import (
    RoutingConstraints,
    RoutingPreference,
)
from brahmastra.domain.routing.router import RoutingEngine


def make_dummy_data():
    now = datetime.now(timezone.utc)
    acc_local = ProviderAccount(
        id=1,
        name="local-ollama",
        provider_type="ollama",
        created_at=now,
        updated_at=now,
    )
    acc_cloud = ProviderAccount(
        id=2,
        name="cloud-openrouter",
        provider_type="openrouter",
        created_at=now,
        updated_at=now,
    )

    m_local = ModelInfo(
        id="llama3:latest",
        name="Llama 3 8B",
        provider="ollama",
        context_window=8192,
        capabilities=[ModelCapability.CHAT, ModelCapability.STREAMING],
        is_local=True,
    )
    m_cloud = ModelInfo(
        id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        provider="openrouter",
        context_window=200000,
        capabilities=[ModelCapability.CHAT, ModelCapability.STREAMING, ModelCapability.VISION],
        is_local=False,
    )

    return [(m_local, acc_local), (m_cloud, acc_cloud)]


def test_routing_local_first_preference():
    """Verify LOCAL_FIRST preference picks local model when eligible."""
    candidates = make_dummy_data()
    router = RoutingEngine()

    decision = router.route(candidates, RoutingConstraints(), RoutingPreference.LOCAL_FIRST)
    assert decision.selected_model_id == "llama3:latest"
    assert decision.selected_account_name == "local-ollama"
    assert "Local runtime" in decision.explanation


def test_routing_cloud_first_preference():
    """Verify CLOUD_FIRST preference picks cloud model."""
    candidates = make_dummy_data()
    router = RoutingEngine()

    decision = router.route(candidates, RoutingConstraints(), RoutingPreference.CLOUD_FIRST)
    assert decision.selected_model_id == "anthropic/claude-3.5-sonnet"
    assert decision.selected_account_name == "cloud-openrouter"


def test_routing_require_local_hard_constraint():
    """Verify require_local=True disqualifies cloud models."""
    candidates = make_dummy_data()
    router = RoutingEngine()

    decision = router.route(
        candidates,
        RoutingConstraints(require_local=True),
        RoutingPreference.CLOUD_FIRST,
    )
    # Must select local even though preference was CLOUD_FIRST because require_local is hard constraint
    assert decision.selected_model_id == "llama3:latest"

    # Cloud model should have disqualification reason
    claude_eval = next(c for c in decision.candidates_evaluated if c.model_id == "anthropic/claude-3.5-sonnet")
    assert claude_eval.is_eligible is False
    assert "require_local=True" in claude_eval.disqualification_reason


def test_routing_min_context_window():
    """Verify min_context_window disqualifies models below threshold."""
    candidates = make_dummy_data()
    router = RoutingEngine()

    # Require 32k context: local (8k) disqualified, cloud (200k) wins
    decision = router.route(
        candidates,
        RoutingConstraints(min_context_window=32768),
        RoutingPreference.LOCAL_FIRST,
    )
    assert decision.selected_model_id == "anthropic/claude-3.5-sonnet"

    local_eval = next(c for c in decision.candidates_evaluated if c.model_id == "llama3:latest")
    assert local_eval.is_eligible is False
    assert "Context window" in local_eval.disqualification_reason


def test_routing_capability_requirement():
    """Verify requiring VISION filters out non-vision models."""
    candidates = make_dummy_data()
    router = RoutingEngine()

    decision = router.route(
        candidates,
        RoutingConstraints(require_capabilities=[ModelCapability.VISION]),
        RoutingPreference.LOCAL_FIRST,
    )
    assert decision.selected_model_id == "anthropic/claude-3.5-sonnet"

    local_eval = next(c for c in decision.candidates_evaluated if c.model_id == "llama3:latest")
    assert local_eval.is_eligible is False
    assert "Missing required capability 'vision'" in local_eval.disqualification_reason


def test_routing_empty_candidates():
    """Verify graceful explanation when no candidates exist."""
    router = RoutingEngine()
    decision = router.route([], RoutingConstraints())
    assert decision.selected_model_id is None
    assert "No provider accounts" in decision.explanation
