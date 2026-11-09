"""
SQLAlchemy ORM models for BRAHMASTRA.
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Helper to return current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class OrganizationModel(Base):
    """Database model for Organizations."""
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    assignments: Mapped[List["OrganizationAssignmentModel"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class ProviderAccountModel(Base):
    """Database model for Provider Accounts."""
    __tablename__ = "provider_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    assignments: Mapped[List["OrganizationAssignmentModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    credentials: Mapped[List["CredentialModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class OrganizationAssignmentModel(Base):
    """Explicit authorization link between an Organization and a ProviderAccount."""
    __tablename__ = "organization_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("provider_accounts.id", ondelete="CASCADE"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    organization: Mapped["OrganizationModel"] = relationship(back_populates="assignments")
    account: Mapped["ProviderAccountModel"] = relationship(back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("organization_id", "account_id", name="uq_org_account"),
    )


class CredentialModel(Base):
    """
    Database model for Credential metadata.
    CRITICAL: Contains ONLY vault references (tickets). NEVER plaintext API keys.
    """
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("provider_accounts.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    vault_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    masked_preview: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    health_status: Mapped[str] = mapped_column(String(32), default="UNVALIDATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    account: Mapped["ProviderAccountModel"] = relationship(back_populates="credentials")

    __table_args__ = (
        UniqueConstraint("account_id", "label", name="uq_account_credential_label"),
    )
