"""
Unit tests for persistent Model Registry caching and discovery.
"""

import pytest
import respx
from sqlalchemy import create_engine
from brahmastra.domain.organizations.models import OrganizationCreate
from brahmastra.domain.credentials.models import ProviderAccountCreate
from brahmastra.application.use_cases.org_use_cases import create_organization
from brahmastra.application.use_cases.credential_use_cases import register_provider_account
from brahmastra.application.use_cases.model_registry_use_cases import (
    sync_models_for_account,
    get_cached_models,
)
from brahmastra.infrastructure.database.models import Base
from brahmastra.infrastructure.vault.memory_vault import InMemoryVault


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")
    vault = InMemoryVault()
    return {"engine": engine, "vault": vault}


@respx.mock
def test_model_registry_sync_and_cache(test_setup):
    """Verify live model sync caches records in SQLite and retrieves them without live API."""
    engine = test_setup["engine"]
    vault = test_setup["vault"]

    # Register org and account
    create_organization(OrganizationCreate(name="dev-org"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="ollama-local", provider_type="ollama", endpoint="http://localhost:11434"),
        assign_to_org_name="dev-org",
        engine=engine,
    )

    # Mock Ollama tags
    respx.get("http://localhost:11434/api/tags").respond(
        status_code=200,
        json={
            "models": [
                {"name": "llama3:latest", "details": {"parameter_size": "8.0B"}},
                {"name": "codellama:7b", "details": {"parameter_size": "7.0B"}},
            ]
        },
    )

    # 1. Sync
    synced = sync_models_for_account("ollama-local", vault=vault, engine=engine)
    assert len(synced) == 2

    # 2. Clear network mock to ensure subsequent queries are 100% from SQLite cache
    respx.clear()

    # 3. Retrieve from SQLite cache
    cached = get_cached_models(org_name="dev-org", engine=engine)
    assert len(cached) == 2
    ids = [m.id for m in cached]
    assert "llama3:latest" in ids
    assert "codellama:7b" in ids
    assert all(m.is_local for m in cached)


def test_model_registry_tenant_isolation(test_setup):
    """Verify organization cannot see cached models of unassigned accounts."""
    engine = test_setup["engine"]
    vault = test_setup["vault"]

    create_organization(OrganizationCreate(name="org-a"), engine=engine)
    create_organization(OrganizationCreate(name="org-b"), engine=engine)

    register_provider_account(
        ProviderAccountCreate(name="acc-a", provider_type="ollama"),
        assign_to_org_name="org-a",
        engine=engine,
    )

    with respx.mock:
        respx.get("http://localhost:11434/api/tags").respond(
            status_code=200,
            json={"models": [{"name": "private-model", "details": {}}]},
        )
        sync_models_for_account("acc-a", vault=vault, engine=engine)

    # Org-A sees private-model
    org_a_models = get_cached_models(org_name="org-a", engine=engine)
    assert len(org_a_models) == 1
    assert org_a_models[0].id == "private-model"

    # Org-B sees ZERO models (strict tenant isolation)
    org_b_models = get_cached_models(org_name="org-b", engine=engine)
    assert len(org_b_models) == 0
