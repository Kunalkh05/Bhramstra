"""
Unit tests for request-level usage records and accounting calculations.
"""

import pytest
from sqlalchemy import create_engine
from brahmastra.domain.organizations.models import OrganizationCreate
from brahmastra.domain.credentials.models import ProviderAccountCreate
from brahmastra.domain.observability.models import UsageRecordCreate
from brahmastra.application.use_cases.org_use_cases import create_organization
from brahmastra.application.use_cases.credential_use_cases import register_provider_account
from brahmastra.application.use_cases.usage_use_cases import (
    record_usage,
    get_usage_summary,
)
from brahmastra.infrastructure.database.models import Base


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")
    return {"engine": engine}


def test_record_usage_and_micro_dollar_precision(test_setup):
    """Verify recording requests and accurate micro-dollar aggregation."""
    engine = test_setup["engine"]

    create_organization(OrganizationCreate(name="corp"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="prod-acc", provider_type="openrouter"),
        assign_to_org_name="corp",
        engine=engine,
    )

    # Record 1: 100 prompt + 50 completion = 150 tokens, $0.001500 (1500 micro-USD)
    rec1 = record_usage(
        UsageRecordCreate(
            org_name="corp",
            account_name="prod-acc",
            model_id="anthropic/claude-3.5-sonnet",
            prompt_tokens=100,
            completion_tokens=50,
            cost_micro_usd=1500,
            latency_ms=450.2,
        ),
        engine=engine,
    )
    assert rec1.total_tokens == 150
    assert rec1.cost_usd == 0.0015

    # Record 2: 200 prompt + 100 completion = 300 tokens, $0.003000 (3000 micro-USD)
    rec2 = record_usage(
        UsageRecordCreate(
            org_name="corp",
            account_name="prod-acc",
            model_id="anthropic/claude-3.5-sonnet",
            prompt_tokens=200,
            completion_tokens=100,
            cost_micro_usd=3000,
            latency_ms=520.1,
        ),
        engine=engine,
    )

    # Aggregate summary
    summary = get_usage_summary(org_name="corp", engine=engine)
    assert summary.total_requests == 2
    assert summary.total_prompt_tokens == 300
    assert summary.total_completion_tokens == 150
    assert summary.total_tokens == 450
    # Exact micro-dollar arithmetic (1500 + 3000 = 4500 micro-USD -> $0.0045)
    assert summary.total_cost_usd == 0.0045

    # Verify model breakdown
    assert len(summary.models) == 1
    m_stat = summary.models[0]
    assert m_stat.model_id == "anthropic/claude-3.5-sonnet"
    assert m_stat.requests == 2
    assert m_stat.total_tokens == 450
    assert m_stat.cost_usd == 0.0045


def test_usage_organization_isolation(test_setup):
    """Verify usage records do not leak across organization scopes."""
    engine = test_setup["engine"]

    create_organization(OrganizationCreate(name="org-1"), engine=engine)
    create_organization(OrganizationCreate(name="org-2"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="acc-1", provider_type="openrouter"),
        assign_to_org_name="org-1",
        engine=engine,
    )
    register_provider_account(
        ProviderAccountCreate(name="acc-2", provider_type="ollama"),
        assign_to_org_name="org-2",
        engine=engine,
    )

    # Record usage for Org 1
    record_usage(
        UsageRecordCreate(
            org_name="org-1",
            account_name="acc-1",
            model_id="claude-3.5",
            prompt_tokens=500,
            completion_tokens=100,
            cost_micro_usd=5000,
        ),
        engine=engine,
    )

    # Org 1 summary
    s1 = get_usage_summary(org_name="org-1", engine=engine)
    assert s1.total_requests == 1
    assert s1.total_tokens == 600

    # Org 2 summary must be 0
    s2 = get_usage_summary(org_name="org-2", engine=engine)
    assert s2.total_requests == 0
    assert s2.total_tokens == 0
    assert s2.total_cost_usd == 0.0
