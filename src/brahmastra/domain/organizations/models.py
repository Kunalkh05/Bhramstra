"""
Domain models for Organizations.
"""

from datetime import datetime
from typing import Optional
import re
from pydantic import BaseModel, Field, field_validator, ConfigDict


class OrganizationCreate(BaseModel):
    """Schema for creating a new organization."""
    name: str = Field(..., min_length=2, max_length=64, description="Unique organization identifier")
    description: Optional[str] = Field(None, max_length=256, description="Optional organization description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned):
            raise ValueError("Organization name must contain only letters, numbers, underscores, and hyphens.")
        return cleaned


class Organization(BaseModel):
    """Domain model representing an organization."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = False
