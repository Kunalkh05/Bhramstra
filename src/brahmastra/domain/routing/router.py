"""
Explainable Routing Engine with hard constraint verification.
Zero HTTP, zero network calls, zero authentication logic, zero raw API keys.
"""

from typing import List, Tuple
from brahmastra.domain.providers.models import ModelInfo
from brahmastra.domain.credentials.models import ProviderAccount
from brahmastra.domain.routing.models import (
    RoutingConstraints,
    RoutingPreference,
    RouteDecision,
    CandidateEvaluation,
)


class RoutingEngine:
    """
    Pure domain routing engine evaluating candidates against constraints and preferences.
    """

    def route(
        self,
        available_models: List[Tuple[ModelInfo, ProviderAccount]],
        constraints: RoutingConstraints,
        preference: RoutingPreference = RoutingPreference.LOCAL_FIRST,
    ) -> RouteDecision:
        """
        Evaluate all candidate models and select the optimal model/account.
        Returns a RouteDecision with detailed transparency for every candidate.
        """
        if not available_models:
            return RouteDecision(
                selected_model_id=None,
                selected_account_name=None,
                selected_provider=None,
                explanation="No provider accounts or models are available for this organization.",
                candidates_evaluated=[],
            )

        evaluations: List[CandidateEvaluation] = []
        eligible: List[Tuple[ModelInfo, ProviderAccount, float]] = []

        for model, account in available_models:
            is_eligible = True
            disqualification_reasons = []

            # Constraint 1: Blocked models
            if model.id in constraints.blocked_models:
                is_eligible = False
                disqualification_reasons.append(f"Model '{model.id}' is explicitly in blocked_models list.")

            # Constraint 2: Local execution requirement
            if constraints.require_local and not model.is_local:
                is_eligible = False
                disqualification_reasons.append("Privacy constraint require_local=True, but model is hosted in Cloud.")

            # Constraint 3: Minimum context window
            if constraints.min_context_window > 0 and model.context_window < constraints.min_context_window:
                is_eligible = False
                disqualification_reasons.append(
                    f"Context window {model.context_window:,} < required minimum {constraints.min_context_window:,} tokens."
                )

            # Constraint 4: Allowed providers
            if constraints.allowed_providers:
                allowed_normalized = [p.lower() for p in constraints.allowed_providers]
                if model.provider.lower() not in allowed_normalized:
                    is_eligible = False
                    disqualification_reasons.append(
                        f"Provider '{model.provider}' not in allowed_providers list ({', '.join(constraints.allowed_providers)})."
                    )

            # Constraint 5: Capabilities requirement
            for req_cap in constraints.require_capabilities:
                if req_cap not in model.capabilities:
                    is_eligible = False
                    disqualification_reasons.append(
                        f"Missing required capability '{req_cap.value}'."
                    )

            score = 0.0
            if is_eligible:
                # Scoring based on preference
                if preference == RoutingPreference.LOCAL_FIRST:
                    score += 100.0 if model.is_local else 20.0
                elif preference == RoutingPreference.CLOUD_FIRST:
                    score += 100.0 if not model.is_local else 20.0
                elif preference == RoutingPreference.LOWEST_COST:
                    # Local models have 0 cost, get max score
                    score += 100.0 if model.is_local else 30.0
                else:  # BALANCED
                    score += 50.0

                # Secondary bonus for larger context window
                score += min(model.context_window / 10000.0, 10.0)
                eligible.append((model, account, score))

            evaluations.append(
                CandidateEvaluation(
                    model_id=model.id,
                    account_name=account.name,
                    provider=model.provider,
                    is_eligible=is_eligible,
                    disqualification_reason="; ".join(disqualification_reasons) if disqualification_reasons else None,
                    score=score,
                )
            )

        if not eligible:
            explanation = (
                f"Evaluated {len(evaluations)} candidate(s), but none met the specified hard constraints "
                f"(require_local={constraints.require_local}, min_context={constraints.min_context_window:,})."
            )
            return RouteDecision(
                selected_model_id=None,
                selected_account_name=None,
                selected_provider=None,
                explanation=explanation,
                candidates_evaluated=evaluations,
            )

        # Sort eligible by score descending
        eligible.sort(key=lambda x: x[2], reverse=True)
        winner_model, winner_account, winner_score = eligible[0]

        # Build fallback chain
        fallback_chain = [f"{m.id} ({acc.name})" for m, acc, _ in eligible[1:4]]

        loc_str = "Local runtime (Zero network / $0.00)" if winner_model.is_local else "Cloud API"
        explanation = (
            f"Selected '{winner_model.id}' via account '{winner_account.name}' ({winner_model.provider}) "
            f"with score {winner_score:.1f}. [{loc_str}]. "
            f"Satisfied all {len(constraints.require_capabilities)} required capabilities and context window requirements. "
            f"Evaluated {len(evaluations)} candidate(s); {len(eligible)} were eligible."
        )

        return RouteDecision(
            selected_model_id=winner_model.id,
            selected_account_name=winner_account.name,
            selected_provider=winner_model.provider,
            explanation=explanation,
            candidates_evaluated=evaluations,
            fallback_chain=fallback_chain,
        )
