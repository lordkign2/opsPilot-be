"""
OpsPilot — Audit Module: ORM Model (Phase 8).

Enterprise-grade tamper-evident audit ledger.
Captures who changed what, when, and both before and after values.
"""

import uuid
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """Immutable audit log for all critical operations."""

    __tablename__ = "audit_logs"

    # ── Who ──────────────────────────────────────────────────
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    business_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # ── What ─────────────────────────────────────────────────
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Before / After Snapshot ──────────────────────────────
    before_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # ── Context ──────────────────────────────────────────────
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
