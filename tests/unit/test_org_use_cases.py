"""
Unit tests for Organization domain models and use cases.
"""

import pytest
from sqlalchemy import create_engine
from pydantic import ValidationError

from brahmastra.domain.organizations.models import OrganizationCreate
from brahmastra.application.use_cases.org_use_cases import (
    create_organization,
    list_organizations,
    get_organization,
    get_active_organization,
    switch_active_organization,
)
from brahmastra.infrastructure.database.models import Base


@pytest.fixture
def test_engine(tmp_path, monkeypatch):
    """Provide an isolated in-memory/temp SQLite engine and state file."""
    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    Base.metadata.create_all(bind=engine)

    # Route config storage to tmp_path
    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))

    return engine


def test_organization_name_validation():
    """Verify validation of organization names."""
    # Valid names
    OrganizationCreate(name="personal")
    OrganizationCreate(name="work_corp-2")

    # Invalid names
    with pytest.raises(ValidationError):
        OrganizationCreate(name="a")  # too short (<2)

    with pytest.raises(ValidationError):
        OrganizationCreate(name="bad name with spaces")

    with pytest.raises(ValidationError):
        OrganizationCreate(name="bad@name!")


def test_create_and_list_organizations(test_engine):
    """Verify creating organizations and listing with active status."""
    org1 = create_organization(
        OrganizationCreate(name="personal", description="Personal projects"),
        engine=test_engine,
    )
    assert org1.name == "personal"
    assert org1.is_active is True  # First org created becomes active

    # Add second org
    org2 = create_organization(
        OrganizationCreate(name="company", description="Work projects"),
        engine=test_engine,
    )
    assert org2.name == "company"
    assert org2.is_active is False

    orgs = list_organizations(engine=test_engine)
    assert len(orgs) == 2
    names = [o.name for o in orgs]
    assert "personal" in names
    assert "company" in names


def test_duplicate_organization_fails(test_engine):
    """Verify creating duplicate org raises ValueError."""
    create_organization(OrganizationCreate(name="team-alpha"), engine=test_engine)
    with pytest.raises(ValueError, match="already exists"):
        create_organization(OrganizationCreate(name="team-alpha"), engine=test_engine)


def test_switch_and_current_organization(test_engine):
    """Verify switching active organization profile."""
    create_organization(OrganizationCreate(name="dev"), engine=test_engine)
    create_organization(OrganizationCreate(name="prod"), engine=test_engine)

    # Initial active is dev
    active = get_active_organization(engine=test_engine)
    assert active is not None
    assert active.name == "dev"

    # Switch to prod
    switched = switch_active_organization("prod", engine=test_engine)
    assert switched.name == "prod"
    assert switched.is_active is True

    current = get_active_organization(engine=test_engine)
    assert current is not None
    assert current.name == "prod"


def test_switch_nonexistent_org_fails(test_engine):
    """Verify switching to nonexistent org raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        switch_active_organization("ghost-org", engine=test_engine)
