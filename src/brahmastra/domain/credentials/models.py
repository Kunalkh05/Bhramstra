"""
Domain models and enums for Providers, ProviderAccounts, and Credentials.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator
import re


class CredentialStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    DISABLED = "DISABLED"


class CredentialHealth(str, Enum):
    HEALTHY = "HEALTHY"
    UNVALIDATED = "UNVALIDATED"
    ERROR = "ERROR"


def mask_secret(secret: str) -> str:
    """
    Generate a non-sensitive preview of a secret string.
    Never reveals the secret body.
    """
    secret = secret.strip()
    if len(secret) <= 8:
        return "********"
    prefix = secret[:4]
    suffix = secret[-4:]
    return f"{prefix}...{suffix}"


class ProviderAccountCreate(BaseModel):
    """Schema for registering a new provider account."""
    name: str = Field(..., min_length=2, max_length=64, description="Unique account identifier")
    provider_type: str = Field(..., description="Provider type (e.g. 'openrouter', 'ollama')")
    endpoint: Optional[str] = Field(None, max_length=256, description="Optional custom base endpoint URL")
    description: Optional[str] = Field(None, max_length=256, description="Optional description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not re.match(r"^[a-z0-9_\-]+$", cleaned):
            raise ValueError("Account name must contain only lowercase letters, numbers, hyphens, and underscores.")
        return cleaned


class ProviderAccount(BaseModel):
    """Domain model for a Provider Account."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider_type: str
    endpoint: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    assigned_org_names: List[str] = []


class CredentialCreate(BaseModel):
    """Schema for creating/adding a credential."""
    account_name: str
    label: str = Field(..., min_length=2, max_length=64)
    secret: str = Field(..., min_length=1)

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not re.match(r"^[a-z0-9_\-]+$", cleaned):
            raise ValueError("Credential label must contain only lowercase letters, numbers, hyphens, and underscores.")
        return cleaned


class CredentialRead(BaseModel):
    """Domain model representing credential metadata. Never contains plaintext secret."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    account_name: str
    label: str
    vault_ref: str
    masked_preview: str
    status: CredentialStatus
    health_status: CredentialHealth
    created_at: datetime
    updated_at: datetime
    last_validated_at: Optional[datetime] = None
