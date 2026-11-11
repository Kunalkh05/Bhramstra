"""
Security test verifying organization isolation and preventing cross-tenant
credential hijacking (BRAH-SEC-001).
"""
import pytest
from sqlalchemy import create_engine

from brahmastra.application.use_cases.credential_use_cases import (
    add_credential,
    list_credentials,
    register_provider_account,
    remove_credential,
    revoke_credential,
    rotate_credential,
    verify_credential,
)
from brahmastra.application.use_cases.org_use_cases import create_organization
from brahmastra.domain.credentials.models import CredentialCreate, ProviderAccountCreate
from brahmastra.domain.organizations.models import OrganizationCreate
from brahmastra.infrastructure.config import set_active_org_name
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


def test_unscoped_caller_cannot_rotate_org_credential(isolated_db_and_vault):
    """Verify an unauthenticated/unscoped caller (org_name=None, active=None) cannot rotate org credentials."""
    engine, vault = isolated_db_and_vault

    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        org_name="org-alpha",
        vault=vault,
        engine=engine,
    )
    set_active_org_name(None)

    # Calling rotate with org_name=None and no active org must fail with PermissionError
    with pytest.raises(PermissionError, match="assigned to an organization"):
        rotate_credential(
            label="prod-key",
            account_name="alpha-acc",
            new_secret="hacked-secret-999",
            org_name=None,
            vault=vault,
            engine=engine,
        )


def test_unscoped_caller_cannot_revoke_org_credential(isolated_db_and_vault):
    """Verify an unscoped caller cannot revoke credentials on an org-assigned account."""
    engine, vault = isolated_db_and_vault

    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        org_name="org-alpha",
        vault=vault,
        engine=engine,
    )
    set_active_org_name(None)

    with pytest.raises(PermissionError, match="assigned to an organization"):
        revoke_credential(
            label="prod-key",
            account_name="alpha-acc",
            org_name=None,
            engine=engine,
        )


def test_unscoped_caller_cannot_remove_org_credential(isolated_db_and_vault):
    """Verify an unscoped caller cannot permanently delete credentials on an org-assigned account."""
    engine, vault = isolated_db_and_vault

    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        org_name="org-alpha",
        vault=vault,
        engine=engine,
    )
    set_active_org_name(None)

    with pytest.raises(PermissionError, match="assigned to an organization"):
        remove_credential(
            label="prod-key",
            account_name="alpha-acc",
            org_name=None,
            vault=vault,
            engine=engine,
        )


def test_unscoped_caller_cannot_verify_org_credential(isolated_db_and_vault):
    """Verify an unscoped caller cannot probe/verify credentials on an org-assigned account."""
    engine, vault = isolated_db_and_vault

    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        org_name="org-alpha",
        vault=vault,
        engine=engine,
    )
    set_active_org_name(None)

    with pytest.raises(PermissionError, match="assigned to an organization"):
        verify_credential(
            label="prod-key",
            account_name="alpha-acc",
            org_name=None,
            vault=vault,
            engine=engine,
        )


def test_unscoped_caller_cannot_add_credential_to_org_account(isolated_db_and_vault):
    """Verify an unscoped caller cannot inject credentials into an org-assigned account."""
    engine, vault = isolated_db_and_vault

    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    set_active_org_name(None)

    with pytest.raises(PermissionError, match="assigned to an organization"):
        add_credential(
            CredentialCreate(account_name="alpha-acc", label="injected", secret="hacker-key"),
            org_name=None,
            vault=vault,
            engine=engine,
        )


def test_unscoped_list_credentials_does_not_leak_org_credentials(isolated_db_and_vault):
    """Verify list_credentials without org context does NOT disclose credentials of org accounts."""
    engine, vault = isolated_db_and_vault

    # Org account with credential
    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="alpha-acc", label="prod-key", secret="alpha-secret-12345"),
        org_name="org-alpha",
        vault=vault,
        engine=engine,
    )
    set_active_org_name(None)

    # Clear active org to simulate unscoped caller
    set_active_org_name(None)

    # Global unassigned account with credential
    register_provider_account(
        ProviderAccountCreate(name="global-acc", provider_type="openrouter"),
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="global-acc", label="local-key", secret="local-secret-999"),
        vault=vault,
        engine=engine,
    )

    # Calling list_credentials with no org context must NOT include alpha-acc
    unscoped_creds = list_credentials(org_name=None, engine=engine)
    account_names = [c.account_name for c in unscoped_creds]
    assert "alpha-acc" not in account_names
    assert "global-acc" in account_names


def test_unassigned_local_test_account_permitted_unscoped(isolated_db_and_vault):
    """Verify unassigned accounts (for local testing) can still operate without org context."""
    engine, vault = isolated_db_and_vault

    register_provider_account(
        ProviderAccountCreate(name="dev-acc", provider_type="openrouter"),
        engine=engine,
    )
    cred = add_credential(
        CredentialCreate(account_name="dev-acc", label="dev-key", secret="dev-secret-000"),
        vault=vault,
        engine=engine,
    )
    assert cred.label == "dev-key"

    rotated = rotate_credential(
        label="dev-key",
        account_name="dev-acc",
        new_secret="new-dev-secret",
        vault=vault,
        engine=engine,
    )
    assert rotated.masked_preview != ""

    verified = verify_credential(label="dev-key", account_name="dev-acc", vault=vault, engine=engine)
    assert verified is True


def test_cross_tenant_account_assignment_blocked(isolated_db_and_vault):
    """Verify Organization B cannot co-opt or assign Organization A's existing provider account."""
    from brahmastra.application.use_cases.credential_use_cases import assign_account_to_organization
    engine, vault = isolated_db_and_vault

    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )

    create_organization(OrganizationCreate(name="org-bravo"), engine=engine)

    # Organization B attempts to assign alpha-acc to org-bravo
    with pytest.raises(PermissionError, match="already assigned to another organization"):
        assign_account_to_organization(
            account_name="alpha-acc",
            org_name="org-bravo",
            engine=engine,
        )


def test_unscoped_list_provider_accounts_does_not_leak_org_accounts(isolated_db_and_vault):
    """Verify calling list_provider_accounts without organization context does not leak org-assigned accounts."""
    from brahmastra.application.use_cases.credential_use_cases import list_provider_accounts
    engine, vault = isolated_db_and_vault

    # Create Org A with assigned account
    create_organization(OrganizationCreate(name="org-alpha"), engine=engine)
    register_provider_account(
        ProviderAccountCreate(name="alpha-private-acc", provider_type="openrouter"),
        assign_to_org_name="org-alpha",
        engine=engine,
    )

    # Create unassigned dev account
    register_provider_account(
        ProviderAccountCreate(name="dev-public-acc", provider_type="openrouter"),
        engine=engine,
    )

    set_active_org_name(None)

    # Unscoped list must ONLY return unassigned account
    unscoped_accounts = list_provider_accounts(org_name=None, engine=engine)
    names = [a.name for a in unscoped_accounts]
    assert "alpha-private-acc" not in names
    assert "dev-public-acc" in names
