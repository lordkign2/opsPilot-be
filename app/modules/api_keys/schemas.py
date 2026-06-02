"""
OpsPilot — API Keys Module: Pydantic Schemas (Phase 8).
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    """Request body for creating a new API key."""

    name: str = Field(..., min_length=1, max_length=100, description="Descriptive name for the key")
    description: str | None = Field(None, max_length=500)
    expires_at: datetime.datetime | None = Field(None, description="Optional expiry datetime (UTC)")


class APIKeyResponse(BaseModel):
    """API key metadata returned in list/get responses (never includes raw key)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    key_hint: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime.datetime | None
    expires_at: datetime.datetime | None
    created_at: datetime.datetime


class APIKeyCreatedResponse(APIKeyResponse):
    """
    Returned **only once** immediately after key creation.
    Includes the raw key — it is never accessible again after this response.
    """

    raw_key: str = Field(..., description="The full API key value. Store it securely — shown only once.")
