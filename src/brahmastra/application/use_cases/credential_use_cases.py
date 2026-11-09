"""
Application use cases for Provider Accounts, Organization Assignments, and Credentials.
"""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy import Engine

from brahmastra.domain.credentials.models import (
    ProviderAccount,
    ProviderAccountCreate,
    CredentialRead,
    CredentialCreate,
    CredentialStatus,
    CredentialHealth,
    mask_secret,
)
from brahmastra.infrastructure.database.models import (
    ProviderAccountModel,
    OrganizationAssignmentModel,
    OrganizationModel,
    CredentialModel,
)
from brahmastra.infrastructure.database.session import get_session
from brahmastra.infrastructure.vault.factory import get_vault
from brahmastra.domain.vault.interface import VaultInterface
from brahmastra.infrastructure.config import get_active_org_name


def _verify_account_organization_scoping(
    session,
    account: ProviderAccountModel,
    org_name: Optional[str] = None,
) -> None:
    """
    Verify that the account is accessible within the given or active organization scope.
    If org_name is provided, or active org is set, ensures the account has an assignment
    to that organization (BRAH-SEC-001).
    """
    target_org = org_name
    if not target_org:
        active = get_active_org_name()
        if active:
            active_org_record = session.scalar(
                select(OrganizationModel).where(OrganizationModel.name == active)
            )
            if active_org_record:
                target_org = active

    if not target_org:
        return

    org = session.scalar(
        select(OrganizationModel).where(OrganizationModel.name == target_org)
    )
    if not org:
        raise ValueError(f"Organization '{target_org}' not found.")

    assignment = session.scalar(
        select(OrganizationAssignmentModel).where(
            OrganizationAssignmentModel.account_id == account.id,
            OrganizationAssignmentModel.organization_id == org.id,
        )
    )
    if not assignment:
        raise PermissionError(
            f"Account '{account.name}' is not assigned to organization '{target_org}'."
        )


def register_provider_account(
    data: ProviderAccountCreate,
    assign_to_org_name: Optional[str] = None,
    engine: Optional[Engine] = None,
) -> ProviderAccount:
    """Register a new provider account and optionally assign it to an organization."""
    with get_session(engine) as session:
        existing = session.scalar(
            select(ProviderAccountModel).where(ProviderAccountModel.name == data.name)
        )
        if existing:
            raise ValueError(f"Provider account '{data.name}' already exists.")

        account = ProviderAccountModel(
            name=data.name,
            provider_type=data.provider_type.lower(),
            endpoint=data.endpoint,
            description=data.description,
        )
        session.add(account)
        session.flush()

        assigned_orgs = []
        if assign_to_org_name:
            org = session.scalar(
                select(OrganizationModel).where(OrganizationModel.name == assign_to_org_name)
            )
            if not org:
                raise ValueError(f"Organization '{assign_to_org_name}' not found.")
            assignment = OrganizationAssignmentModel(
                organization_id=org.id,
                account_id=account.id,
            )
            session.add(assignment)
            session.flush()
            assigned_orgs.append(org.name)

        return ProviderAccount(
            id=account.id,
            name=account.name,
            provider_type=account.provider_type,
            endpoint=account.endpoint,
            description=account.description,
            created_at=account.created_at,
            updated_at=account.updated_at,
            assigned_org_names=assigned_orgs,
        )


def list_provider_accounts(
    org_name: Optional[str] = None,
    engine: Optional[Engine] = None,
) -> List[ProviderAccount]:
    """
    List provider accounts.
    If org_name is specified, returns ONLY accounts explicitly assigned to that organization.
    """
    with get_session(engine) as session:
        if org_name:
            org = session.scalar(
                select(OrganizationModel).where(OrganizationModel.name == org_name)
            )
            if not org:
                raise ValueError(f"Organization '{org_name}' not found.")

            stmt = (
                select(ProviderAccountModel)
                .join(OrganizationAssignmentModel, OrganizationAssignmentModel.account_id == ProviderAccountModel.id)
                .where(OrganizationAssignmentModel.organization_id == org.id)
                .options(selectinload(ProviderAccountModel.assignments).selectinload(OrganizationAssignmentModel.organization))
            )
        else:
            stmt = (
                select(ProviderAccountModel)
                .options(selectinload(ProviderAccountModel.assignments).selectinload(OrganizationAssignmentModel.organization))
            )

        records = session.scalars(stmt).all()
        return [
            ProviderAccount(
                id=r.id,
                name=r.name,
                provider_type=r.provider_type,
                endpoint=r.endpoint,
                description=r.description,
                created_at=r.created_at,
                updated_at=r.updated_at,
                assigned_org_names=[a.organization.name for a in r.assignments if a.organization],
            )
            for r in records
        ]


def assign_account_to_organization(
    account_name: str,
    org_name: str,
    engine: Optional[Engine] = None,
) -> None:
    """Explicitly assign a provider account to an organization."""
    with get_session(engine) as session:
        account = session.scalar(
            select(ProviderAccountModel).where(ProviderAccountModel.name == account_name)
        )
        if not account:
            raise ValueError(f"Provider account '{account_name}' not found.")

        org = session.scalar(
            select(OrganizationModel).where(OrganizationModel.name == org_name)
        )
        if not org:
            raise ValueError(f"Organization '{org_name}' not found.")

        existing = session.scalar(
            select(OrganizationAssignmentModel).where(
                OrganizationAssignmentModel.account_id == account.id,
                OrganizationAssignmentModel.organization_id == org.id,
            )
        )
        if existing:
            return  # Already assigned

        assignment = OrganizationAssignmentModel(
            organization_id=org.id,
            account_id=account.id,
        )
        session.add(assignment)


def add_credential(
    data: CredentialCreate,
    org_name: Optional[str] = None,
    vault: Optional[VaultInterface] = None,
    engine: Optional[Engine] = None,
) -> CredentialRead:
    """
    Store credential secret in the OS Vault and record metadata in SQLite.
    Never persists plaintext secrets in the database.
    """
    v = vault or get_vault()
    with get_session(engine) as session:
        account = session.scalar(
            select(ProviderAccountModel).where(ProviderAccountModel.name == data.account_name)
        )
        if not account:
            raise ValueError(f"Provider account '{data.account_name}' not found.")

        _verify_account_organization_scoping(session, account, org_name)

        existing = session.scalar(
            select(CredentialModel).where(
                CredentialModel.account_id == account.id,
                CredentialModel.label == data.label,
            )
        )
        if existing:
            raise ValueError(
                f"Credential '{data.label}' already exists for account '{data.account_name}'."
            )

        # Store in vault
        service_name = f"brahmastra:{account.provider_type}"
        account_slot = f"{account.name}:{data.label}"
        vault_ref = v.store_secret(service_name, account_slot, data.secret)

        now = datetime.now(timezone.utc)
        record = CredentialModel(
            account_id=account.id,
            label=data.label,
            vault_ref=vault_ref,
            masked_preview=mask_secret(data.secret),
            status=CredentialStatus.ACTIVE.value,
            health_status=CredentialHealth.HEALTHY.value,
            last_validated_at=now,
        )
        session.add(record)
        session.flush()

        return CredentialRead(
            id=record.id,
            account_id=account.id,
            account_name=account.name,
            label=record.label,
            vault_ref=record.vault_ref,
            masked_preview=record.masked_preview,
            status=CredentialStatus(record.status),
            health_status=CredentialHealth(record.health_status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_validated_at=record.last_validated_at,
        )


def list_credentials(
    account_name: Optional[str] = None,
    org_name: Optional[str] = None,
    engine: Optional[Engine] = None,
) -> List[CredentialRead]:
    """List credentials with masked previews and health statuses."""
    with get_session(engine) as session:
        stmt = (
            select(CredentialModel, ProviderAccountModel.name)
            .join(ProviderAccountModel, ProviderAccountModel.id == CredentialModel.account_id)
        )

        if account_name:
            stmt = stmt.where(ProviderAccountModel.name == account_name)

        if org_name:
            org = session.scalar(
                select(OrganizationModel).where(OrganizationModel.name == org_name)
            )
            if not org:
                raise ValueError(f"Organization '{org_name}' not found.")
            stmt = stmt.join(
                OrganizationAssignmentModel,
                OrganizationAssignmentModel.account_id == ProviderAccountModel.id,
            ).where(OrganizationAssignmentModel.organization_id == org.id)

        rows = session.execute(stmt).all()
        return [
            CredentialRead(
                id=c.id,
                account_id=c.account_id,
                account_name=acc_name,
                label=c.label,
                vault_ref=c.vault_ref,
                masked_preview=c.masked_preview,
                status=CredentialStatus(c.status),
                health_status=CredentialHealth(c.health_status),
                created_at=c.created_at,
                updated_at=c.updated_at,
                last_validated_at=c.last_validated_at,
            )
            for c, acc_name in rows
        ]


def verify_credential(
    label: str,
    account_name: str,
    org_name: Optional[str] = None,
    vault: Optional[VaultInterface] = None,
    engine: Optional[Engine] = None,
) -> bool:
    """Verify that the secret exists in the OS Vault."""
    v = vault or get_vault()
    with get_session(engine) as session:
        account = session.scalar(
            select(ProviderAccountModel).where(ProviderAccountModel.name == account_name)
        )
        if not account:
            raise ValueError(f"Provider account '{account_name}' not found.")

        _verify_account_organization_scoping(session, account, org_name)

        cred = session.scalar(
            select(CredentialModel).where(
                CredentialModel.account_id == account.id,
                CredentialModel.label == label,
            )
        )
        if not cred:
            raise ValueError(f"Credential '{label}' not found for account '{account_name}'.")

        service_name = f"brahmastra:{account.provider_type}"
        account_slot = f"{account.name}:{cred.label}"
        has_secret = v.has_secret(service_name, account_slot)

        cred.last_validated_at = datetime.now(timezone.utc)
        cred.health_status = CredentialHealth.HEALTHY.value if has_secret else CredentialHealth.ERROR.value
        return has_secret


def rotate_credential(
    label: str,
    account_name: str,
    new_secret: str,
    org_name: Optional[str] = None,
    vault: Optional[VaultInterface] = None,
    engine: Optional[Engine] = None,
) -> CredentialRead:
    """Rotate an existing credential with a new secret value in the OS Vault."""
    v = vault or get_vault()
    with get_session(engine) as session:
        account = session.scalar(
            select(ProviderAccountModel).where(ProviderAccountModel.name == account_name)
        )
        if not account:
            raise ValueError(f"Provider account '{account_name}' not found.")

        _verify_account_organization_scoping(session, account, org_name)

        cred = session.scalar(
            select(CredentialModel).where(
                CredentialModel.account_id == account.id,
                CredentialModel.label == label,
            )
        )
        if not cred:
            raise ValueError(f"Credential '{label}' not found for account '{account_name}'.")

        service_name = f"brahmastra:{account.provider_type}"
        account_slot = f"{account.name}:{cred.label}"
        v.store_secret(service_name, account_slot, new_secret)

        now = datetime.now(timezone.utc)
        cred.masked_preview = mask_secret(new_secret)
        cred.status = CredentialStatus.ACTIVE.value
        cred.health_status = CredentialHealth.HEALTHY.value
        cred.last_validated_at = now
        cred.updated_at = now

        return CredentialRead(
            id=cred.id,
            account_id=account.id,
            account_name=account.name,
            label=cred.label,
            vault_ref=cred.vault_ref,
            masked_preview=cred.masked_preview,
            status=CredentialStatus(cred.status),
            health_status=CredentialHealth(cred.health_status),
            created_at=cred.created_at,
            updated_at=cred.updated_at,
            last_validated_at=cred.last_validated_at,
        )


def revoke_credential(
    label: str,
    account_name: str,
    org_name: Optional[str] = None,
    engine: Optional[Engine] = None,
) -> CredentialRead:
    """Revoke a credential. Revoked credentials cannot be used for inference."""
    with get_session(engine) as session:
        account = session.scalar(
            select(ProviderAccountModel).where(ProviderAccountModel.name == account_name)
        )
        if not account:
            raise ValueError(f"Provider account '{account_name}' not found.")

        _verify_account_organization_scoping(session, account, org_name)

        cred = session.scalar(
            select(CredentialModel).where(
                CredentialModel.account_id == account.id,
                CredentialModel.label == label,
            )
        )
        if not cred:
            raise ValueError(f"Credential '{label}' not found for account '{account_name}'.")

        cred.status = CredentialStatus.REVOKED.value
        cred.updated_at = datetime.now(timezone.utc)

        return CredentialRead(
            id=cred.id,
            account_id=account.id,
            account_name=account.name,
            label=cred.label,
            vault_ref=cred.vault_ref,
            masked_preview=cred.masked_preview,
            status=CredentialStatus.REVOKED,
            health_status=CredentialHealth(cred.health_status),
            created_at=cred.created_at,
            updated_at=cred.updated_at,
            last_validated_at=cred.last_validated_at,
        )


def remove_credential(
    label: str,
    account_name: str,
    org_name: Optional[str] = None,
    vault: Optional[VaultInterface] = None,
    engine: Optional[Engine] = None,
) -> bool:
    """Permanently delete a credential from the OS Vault and database."""
    v = vault or get_vault()
    with get_session(engine) as session:
        account = session.scalar(
            select(ProviderAccountModel).where(ProviderAccountModel.name == account_name)
        )
        if not account:
            raise ValueError(f"Provider account '{account_name}' not found.")

        _verify_account_organization_scoping(session, account, org_name)

        cred = session.scalar(
            select(CredentialModel).where(
                CredentialModel.account_id == account.id,
                CredentialModel.label == label,
            )
        )
        if not cred:
            raise ValueError(f"Credential '{label}' not found for account '{account_name}'.")

        service_name = f"brahmastra:{account.provider_type}"
        account_slot = f"{account.name}:{cred.label}"
        v.delete_secret(service_name, account_slot)

        session.delete(cred)
        return True
