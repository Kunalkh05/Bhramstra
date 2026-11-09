"""
Application use cases for Organization management.
"""

from typing import List, Optional
from sqlalchemy import select, Engine

from brahmastra.domain.organizations.models import Organization, OrganizationCreate
from brahmastra.infrastructure.config import get_active_org_name, set_active_org_name
from brahmastra.infrastructure.database.models import OrganizationModel
from brahmastra.infrastructure.database.session import get_session


def create_organization(data: OrganizationCreate, engine: Optional[Engine] = None) -> Organization:
    """
    Create a new organization workspace.
    Raises ValueError if an organization with the same name already exists.
    """
    with get_session(engine) as session:
        existing = session.scalar(
            select(OrganizationModel).where(OrganizationModel.name == data.name)
        )
        if existing:
            raise ValueError(f"Organization '{data.name}' already exists.")

        org_record = OrganizationModel(
            name=data.name,
            description=data.description,
        )
        session.add(org_record)
        session.flush()

        active_name = get_active_org_name()
        # If no active organization is currently set, make this newly created one active
        if not active_name:
            set_active_org_name(data.name)
            is_active = True
        else:
            is_active = (active_name == data.name)

        return Organization(
            id=org_record.id,
            name=org_record.name,
            description=org_record.description,
            created_at=org_record.created_at,
            updated_at=org_record.updated_at,
            is_active=is_active,
        )


def list_organizations(engine: Optional[Engine] = None) -> List[Organization]:
    """
    List all registered organizations with active state indicator.
    """
    active_name = get_active_org_name()
    with get_session(engine) as session:
        records = session.scalars(
            select(OrganizationModel).order_by(OrganizationModel.name.asc())
        ).all()

        return [
            Organization(
                id=r.id,
                name=r.name,
                description=r.description,
                created_at=r.created_at,
                updated_at=r.updated_at,
                is_active=(r.name == active_name),
            )
            for r in records
        ]


def get_organization(name: str, engine: Optional[Engine] = None) -> Organization:
    """
    Retrieve details for a specific organization by name.
    """
    active_name = get_active_org_name()
    with get_session(engine) as session:
        record = session.scalar(
            select(OrganizationModel).where(OrganizationModel.name == name)
        )
        if not record:
            raise ValueError(f"Organization '{name}' not found.")

        return Organization(
            id=record.id,
            name=record.name,
            description=record.description,
            created_at=record.created_at,
            updated_at=record.updated_at,
            is_active=(record.name == active_name),
        )


def get_active_organization(engine: Optional[Engine] = None) -> Optional[Organization]:
    """
    Get the currently active organization, or None if none selected.
    """
    active_name = get_active_org_name()
    if not active_name:
        return None
    try:
        return get_organization(active_name, engine)
    except ValueError:
        return None


def switch_active_organization(name: str, engine: Optional[Engine] = None) -> Organization:
    """
    Switch the active organization profile to the specified organization.
    """
    org = get_organization(name, engine)
    set_active_org_name(org.name)
    org.is_active = True
    return org
