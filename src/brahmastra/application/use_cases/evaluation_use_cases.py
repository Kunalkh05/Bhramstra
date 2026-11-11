"""
Application use cases for running benchmark evaluations and listing test suites.
"""
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from brahmastra.domain.evaluation.benchmarks import (
    get_benchmark_suite,
    get_canonical_benchmark_suites,
)
from brahmastra.domain.evaluation.evaluator import EvaluationEngine
from brahmastra.domain.evaluation.models import BenchmarkReport, BenchmarkSuite
from brahmastra.infrastructure.providers.factory import get_provider_adapter
from brahmastra.infrastructure.config import get_active_org_name
from brahmastra.infrastructure.database.session import get_session
from brahmastra.infrastructure.database.models import (
    CredentialModel,
    OrganizationAssignmentModel,
    OrganizationModel,
    ProviderAccountModel,
)
from brahmastra.infrastructure.vault.factory import get_vault


def list_benchmark_suites() -> List[BenchmarkSuite]:
    """Returns all available benchmark suites."""
    return list(get_canonical_benchmark_suites().values())


def evaluate_model_on_suite(
    suite_id: str,
    model_id: str,
    provider_name: str = "ollama",
    org_name: Optional[str] = None,
) -> BenchmarkReport:
    """
    Executes a benchmark suite against a target model with ephemeral credential injection.
    """
    suite = get_benchmark_suite(suite_id)
    if not suite:
        raise ValueError(f"Benchmark suite '{suite_id}' not found.")

    target_org = org_name or get_active_org_name()
    api_key: Optional[str] = None
    account_label = f"{provider_name}-main"

    with get_session() as session:
        # Check if organization and provider assignment exists
        if target_org:
            org = session.query(OrganizationModel).filter_by(name=target_org).first()
            if org:
                # Find matching provider account
                account = (
                    session.query(ProviderAccountModel)
                    .join(
                        OrganizationAssignmentModel,
                        OrganizationAssignmentModel.account_id == ProviderAccountModel.id,
                    )
                    .filter(
                        OrganizationAssignmentModel.organization_id == org.id,
                        ProviderAccountModel.provider_type == provider_name.lower(),
                    )
                    .first()
                )
                if account:
                    # Find active credential
                    cred = (
                        session.query(CredentialModel)
                        .filter_by(account_id=account.id, status="ACTIVE")
                        .first()
                    )
                    if cred:
                        vault = get_vault()
                        service_name = f"brahmastra:{account.provider_type}"
                        api_key = vault.get_secret(service=service_name, account=account.name)

    adapter = get_provider_adapter(provider_name.lower())
    return EvaluationEngine.run_suite(
        suite=suite,
        model_id=model_id,
        adapter=adapter,
        api_key=api_key,
    )


def export_benchmark_report_as_dict(report: BenchmarkReport) -> Dict[str, Any]:
    """Converts a BenchmarkReport into JSON-serializable dictionary."""
    data = asdict(report)
    data["evaluated_at"] = report.evaluated_at.isoformat()
    return data
