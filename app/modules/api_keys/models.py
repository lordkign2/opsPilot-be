"""
OpsPilot — API Keys Module: ORM Model (Phase 8).

Stores SHA-256 hashed API keys — the raw key is NEVER persisted.
Keys use the `opk_` prefix for easy identification in logs/headers.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class APIKey(Base):
    """
    Represents a third-party API key for server-to-server integrations.

    The raw key value is returned **only once** on creation and never stored.
    The ``key_hash`` column stores the SHA-256 hex digest used for lookup.
    """

    __tablename__ = "api_keys"

    # ── Identification ────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_hint: Mapped[str] = mapped_column(String(12), nullable=False)  # last 4 chars for display

    # ── Ownership ─────────────────────────────────────────────
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # ── State ─────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Optional permission scoping (future extensibility) ────
    # Null = inherits full role permissions; non-null = restricted to listed permissions.
    scoped_permissions: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)

    # ── Metadata ─────────────────────────────────────────────
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
