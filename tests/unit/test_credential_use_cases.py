"""
Unit tests for Provider Accounts, Organization Assignments, and Credential Use Cases.
"""

import pytest
from sqlalchemy import create_engine
from brahmastra.domain.credentials.models import (
    ProviderAccountCreate,
    CredentialCreate,
    CredentialStatus,
    CredentialHealth,
)
from brahmastra.domain.organizations.models import OrganizationCreate
from brahmastra.application.use_cases.org_use_cases import create_organization
from brahmastra.application.use_cases.credential_use_cases import (
    register_provider_account,
    list_provider_accounts,
    add_credential,
    list_credentials,
    verify_credential,
    rotate_credential,
    revoke_credential,
    remove_credential,
)
from brahmastra.infrastructure.database.models import Base
from brahmastra.infrastructure.vault.memory_vault import InMemoryVault


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    """Isolated database and memory vault."""
    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")
    vault = InMemoryVault()

    return {"engine": engine, "vault": vault}


def test_provider_account_lifecycle_and_org_isolation(test_setup):
    """Verify provider accounts and organization boundaries."""
    engine = test_setup["engine"]

    # Create two organizations
    create_organization(OrganizationCreate(name="org-personal"), engine=engine)
    create_organization(OrganizationCreate(name="org-work"), engine=engine)

    # Register openrouter account assigned to org-personal
    acc1 = register_provider_account(
        ProviderAccountCreate(
            name="openrouter-personal",
            provider_type="openrouter",
            description="Personal openrouter key",
        ),
        assign_to_org_name="org-personal",
        engine=engine,
    )
    assert acc1.name == "openrouter-personal"
    assert "org-personal" in acc1.assigned_org_names

    # Register ollama account assigned to org-work
    acc2 = register_provider_account(
        ProviderAccountCreate(
            name="ollama-work",
            provider_type="ollama",
            endpoint="http://localhost:11434",
        ),
        assign_to_org_name="org-work",
        engine=engine,
    )
    assert acc2.name == "ollama-work"

    # Verify organization isolation:
    # org-personal sees ONLY openrouter-personal
    personal_accs = list_provider_accounts(org_name="org-personal", engine=engine)
    assert len(personal_accs) == 1
    assert personal_accs[0].name == "openrouter-personal"

    # org-work sees ONLY ollama-work
    work_accs = list_provider_accounts(org_name="org-work", engine=engine)
    assert len(work_accs) == 1
    assert work_accs[0].name == "ollama-work"


def test_credential_lifecycle_and_vault_storage(test_setup):
    """Verify credential creation, rotation, revocation, and removal without leaking secrets."""
    engine = test_setup["engine"]
    vault = test_setup["vault"]

    # Register account
    register_provider_account(
        ProviderAccountCreate(name="test-acc", provider_type="openrouter"),
        engine=engine,
    )

    # 1. Add credential
    raw_secret = "sk-or-v1-abc123xyz789"
    cred = add_credential(
        CredentialCreate(account_name="test-acc", label="primary", secret=raw_secret),
        vault=vault,
        engine=engine,
    )

    assert cred.label == "primary"
    assert cred.vault_ref == "vault:brahmastra:openrouter:test-acc:primary"
    assert cred.masked_preview == "sk-o...z789"
    assert cred.status == CredentialStatus.ACTIVE
    assert cred.health_status == CredentialHealth.HEALTHY

    # Verify vault actually has the secret
    stored_secret = vault.get_secret("brahmastra:openrouter", "test-acc:primary")
    assert stored_secret == raw_secret

    # 2. Test credential
    is_valid = verify_credential("primary", account_name="test-acc", vault=vault, engine=engine)
    assert is_valid is True

    # 3. Rotate credential
    new_raw = "sk-or-v1-new9999key"
    rotated = rotate_credential("primary", account_name="test-acc", new_secret=new_raw, vault=vault, engine=engine)
    assert rotated.masked_preview == "sk-o...9key"
    assert vault.get_secret("brahmastra:openrouter", "test-acc:primary") == new_raw

    # 4. Revoke credential
    revoked = revoke_credential("primary", account_name="test-acc", engine=engine)
    assert revoked.status == CredentialStatus.REVOKED

    # 5. Remove credential
    removed = remove_credential("primary", account_name="test-acc", vault=vault, engine=engine)
    assert removed is True
    assert vault.get_secret("brahmastra:openrouter", "test-acc:primary") is None

    # Listing should now be empty
    creds = list_credentials(account_name="test-acc", engine=engine)
    assert len(creds) == 0
