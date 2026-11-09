"""
Application use cases for persistent Model Registry caching and discovery.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy import Engine

from brahmastra.domain.providers.models import ModelInfo, ModelCapability
from brahmastra.infrastructure.database.models import (
    ProviderAccountModel,
    CachedModelModel,
    OrganizationModel,
    OrganizationAssignmentModel,
    CredentialModel,
)
from brahmastra.infrastructure.database.session import get_session
from brahmastra.infrastructure.providers.factory import get_provider_adapter
from brahmastra.infrastructure.vault.factory import get_vault
from brahmastra.domain.vault.interface import VaultInterface


def sync_models_for_account(
    account_name: str,
    vault: Optional[VaultInterface] = None,
    engine: Optional[Engine] = None,
) -> List[ModelInfo]:
    """
    Fetch live model catalog from provider and update SQLite cache.
    """
    v = vault or get_vault()
    with get_session(engine) as session:
        account = session.scalar(
            select(ProviderAccountModel)
            .where(ProviderAccountModel.name == account_name)
            .options(selectinload(ProviderAccountModel.credentials))
        )
        if not account:
            raise ValueError(f"Provider account '{account_name}' not found.")

        # Resolve secret if active credential exists
        secret = None
        active_creds = [c for c in account.credentials if c.status == "ACTIVE"]
        if active_creds:
            first_c = active_creds[0]
            service_name = f"brahmastra:{account.provider_type}"
            account_slot = f"{account.name}:{first_c.label}"
            secret = v.get_secret(service_name, account_slot)

        adapter = get_provider_adapter(account.provider_type, endpoint=account.endpoint)
        live_models = adapter.list_models(secret=secret)

        # Clear existing cached models for this account to keep catalog clean
        session.execute(
            delete(CachedModelModel).where(CachedModelModel.account_id == account.id)
        )

        now = datetime.now(timezone.utc)
        for m in live_models:
            caps_str = ",".join([c.value for c in m.capabilities])
            cached_rec = CachedModelModel(
                account_id=account.id,
                model_id=m.id,
                name=m.name,
                context_window=m.context_window,
                capabilities=caps_str,
                is_local=m.is_local,
                synced_at=now,
            )
            session.add(cached_rec)

        return live_models


def get_cached_models(
    org_name: Optional[str] = None,
    account_name: Optional[str] = None,
    engine: Optional[Engine] = None,
) -> List[ModelInfo]:
    """
    Retrieve cached models with tenant isolation.
    """
    with get_session(engine) as session:
        stmt = (
            select(CachedModelModel, ProviderAccountModel.provider_type)
            .join(ProviderAccountModel, ProviderAccountModel.id == CachedModelModel.account_id)
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

        results: List[ModelInfo] = []
        for rec, provider_type in rows:
            caps = []
            for c_str in rec.capabilities.split(","):
                c_str = c_str.strip()
                if c_str:
                    try:
                        caps.append(ModelCapability(c_str))
                    except ValueError:
                        pass

            results.append(
                ModelInfo(
                    id=rec.model_id,
                    name=rec.name,
                    provider=provider_type,
                    context_window=rec.context_window,
                    capabilities=caps,
                    is_local=rec.is_local,
                )
            )
        return results
