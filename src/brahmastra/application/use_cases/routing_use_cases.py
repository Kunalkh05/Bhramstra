"""
Application use cases for Explainable Routing and Routed Execution.
"""

from typing import Optional, Tuple, List
import time
from sqlalchemy import Engine

from brahmastra.domain.routing.models import (
    RoutingConstraints,
    RoutingPreference,
    RouteDecision,
)
from brahmastra.domain.routing.router import RoutingEngine
from brahmastra.domain.providers.models import GenerationRequest, GenerationResponse
from brahmastra.domain.observability.models import UsageRecordCreate
from brahmastra.application.use_cases.credential_use_cases import (
    list_provider_accounts,
    list_credentials,
)
from brahmastra.application.use_cases.model_registry_use_cases import get_cached_models
from brahmastra.application.use_cases.usage_use_cases import record_usage
from brahmastra.infrastructure.providers.factory import get_provider_adapter
from brahmastra.infrastructure.vault.factory import get_vault
from brahmastra.domain.vault.interface import VaultInterface


def resolve_route(
    org_name: str,
    constraints: Optional[RoutingConstraints] = None,
    preference: RoutingPreference = RoutingPreference.LOCAL_FIRST,
    engine: Optional[Engine] = None,
) -> RouteDecision:
    """
    Resolve the optimal candidate model and account for an organization.
    The routing engine NEVER receives raw secrets.
    """
    active_constraints = constraints or RoutingConstraints()

    # 1. Tenant boundary: retrieve ONLY accounts assigned to org_name
    accounts = list_provider_accounts(org_name=org_name, engine=engine)
    if not accounts:
        return RouteDecision(
            explanation=f"Organization '{org_name}' has no authorized provider accounts.",
            candidates_evaluated=[],
        )

    acc_map = {a.name: a for a in accounts}

    # 2. Retrieve cached models for these authorized accounts
    models = get_cached_models(org_name=org_name, engine=engine)
    if not models:
        return RouteDecision(
            explanation=(
                f"No models are cached in SQLite for organization '{org_name}'. "
                "Run 'brahmastra models sync' to populate the catalog."
            ),
            candidates_evaluated=[],
        )

    # 3. Pair (model, account) without secrets
    paired_candidates = []
    for m in models:
        # Find which account provides this model
        for acc in accounts:
            if acc.provider_type == m.provider:
                paired_candidates.append((m, acc))
                break

    # 4. Pure domain routing calculation
    engine_router = RoutingEngine()
    return engine_router.route(paired_candidates, active_constraints, preference)


def execute_routed_request(
    org_name: str,
    request: GenerationRequest,
    constraints: Optional[RoutingConstraints] = None,
    preference: RoutingPreference = RoutingPreference.LOCAL_FIRST,
    vault: Optional[VaultInterface] = None,
    engine: Optional[Engine] = None,
) -> Tuple[GenerationResponse, RouteDecision]:
    """
    Route a request, securely inject the required secret from Vault, and execute generation.
    """
    decision = resolve_route(org_name, constraints, preference, engine=engine)
    if not decision.selected_model_id or not decision.selected_account_name:
        raise ValueError(f"Routing failed: {decision.explanation}")

    # Set requested model ID to the routed winner
    request.model = decision.selected_model_id

    # Retrieve credentials for the selected account
    v = vault or get_vault()
    accounts = list_provider_accounts(org_name=org_name, engine=engine)
    target_acc = next((a for a in accounts if a.name == decision.selected_account_name), None)
    if not target_acc:
        raise ValueError(f"Selected account '{decision.selected_account_name}' is not accessible.")

    creds = list_credentials(account_name=target_acc.name, engine=engine)
    active_creds = [c for c in creds if c.status.value == "ACTIVE"]

    secret = None
    if active_creds:
        c = active_creds[0]
        service_name = f"brahmastra:{target_acc.provider_type}"
        account_slot = f"{target_acc.name}:{c.label}"
        secret = v.get_secret(service_name, account_slot)

    # Dispatch to provider adapter
    adapter = get_provider_adapter(target_acc.provider_type, endpoint=target_acc.endpoint)
    start_time = time.perf_counter()
    response = adapter.generate(request, secret=secret)
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # Record token usage
    record_usage(
        UsageRecordCreate(
            org_name=org_name,
            account_name=target_acc.name,
            model_id=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            cost_micro_usd=0,  # 0 for free/local/standard until billing lookup
            latency_ms=round(latency_ms, 2),
        ),
        engine=engine,
    )

    return response, decision
