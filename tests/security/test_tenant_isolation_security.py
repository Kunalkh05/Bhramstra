"""
Security test verifying organization isolation and preventing cross-tenant
credential hijacking (BRAH-SEC-001).
"""
import pytest
from sqlalchemy import create_engine

from brahmastra.application.use_cases.credential_use_cases import (
    add_credential,
    register_provider_account,
    remove_credential,
    revoke_credential,
    rotate_credential,
    verify_credential,
)
from brahmastra.application.use_cases.org_use_cases import create_organization
from brahmastra.domain.credentials.models import CredentialCreate, ProviderAccountCreate
from brahmastra.domain.organizations.models import OrganizationCreate
from brahmastra.infrastructure.database.models import Base
from brahmastra.infrastructure.vault.memory_vault import InMemoryVault


@pytest.fixture
def isolated_db_and_vault(tmp_path, monkeypatch):
    """Provides a fresh in-memory SQLite database and isolated vault."""
    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    vault = InMemoryVault()
    return engine, vault


def test_cross_tenant_credential_rotation_blocked(isolated_db_and_vault):
    """Verify Organization B cannot rotate credentials belonging to Organization A."""
    engine, vault = isolated_db_and_vault

    # Org A setup
    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        vault=vault,
        engine=engine,
    )

    # Org B setup
    create_organization(OrganizationCreate(name="org-bravo"), engine=engine)

    # Org B attempts to rotate Org A's credential -> MUST be blocked with PermissionError
    with pytest.raises(PermissionError, match="not assigned to organization"):
        rotate_credential(
            label="prod-key",
            account_name="alpha-acc",
            new_secret="hacked-secret-999",
            org_name="org-bravo",
            vault=vault,
            engine=engine,
        )

    # Verify Org A's secret remains intact and unchanged
    secret = vault.get_secret("brahmastra:openrouter", "alpha-acc:prod-key")
    assert secret == "alpha-secret-12345"


def test_cross_tenant_credential_revocation_blocked(isolated_db_and_vault):
    """Verify Organization B cannot revoke credentials belonging to Organization A."""
    engine, vault = isolated_db_and_vault

    # Org A setup
    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        vault=vault,
        engine=engine,
    )

    # Org B setup
    create_organization(OrganizationCreate(name="org-bravo"), engine=engine)

    # Org B attempts to revoke Org A's credential -> MUST be blocked with PermissionError
    with pytest.raises(PermissionError, match="not assigned to organization"):
        revoke_credential(
            label="prod-key",
            account_name="alpha-acc",
            org_name="org-bravo",
            engine=engine,
        )


def test_cross_tenant_credential_removal_blocked(isolated_db_and_vault):
    """Verify Organization B cannot delete credentials belonging to Organization A."""
    engine, vault = isolated_db_and_vault

    # Org A setup
    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        vault=vault,
        engine=engine,
    )

    # Org B setup
    create_organization(OrganizationCreate(name="org-bravo"), engine=engine)

    # Org B attempts to remove Org A's credential -> MUST be blocked with PermissionError
    with pytest.raises(PermissionError, match="not assigned to organization"):
        remove_credential(
            label="prod-key",
            account_name="alpha-acc",
            org_name="org-bravo",
            vault=vault,
            engine=engine,
        )


def test_cross_tenant_credential_verification_blocked(isolated_db_and_vault):
    """Verify Organization B cannot probe/verify credentials belonging to Organization A."""
    engine, vault = isolated_db_and_vault

    # Org A setup
    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        vault=vault,
        engine=engine,
    )

    # Org B setup
    create_organization(OrganizationCreate(name="org-bravo"), engine=engine)

    # Org B attempts to verify Org A's credential -> MUST be blocked with PermissionError
    with pytest.raises(PermissionError, match="not assigned to organization"):
        verify_credential(
            label="prod-key",
            account_name="alpha-acc",
            org_name="org-bravo",
            vault=vault,
            engine=engine,
        )


def test_cross_tenant_credential_addition_blocked(isolated_db_and_vault):
    """Verify Organization B cannot inject/add credentials into Organization A's account."""
    engine, vault = isolated_db_and_vault

    # Org A setup
    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )

    # Org B setup
    create_organization(OrganizationCreate(name="org-bravo"), engine=engine)

    # Org B attempts to add a credential under Org A's account
    with pytest.raises(PermissionError, match="not assigned to organization"):
        add_credential(
            CredentialCreate(account_name="alpha-acc", label="injected-key", secret="hacker-secret-666"),
            org_name="org-bravo",
            vault=vault,
            engine=engine,
        )
