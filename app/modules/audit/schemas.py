"""
OpsPilot — Audit Module: Pydantic Schemas (Phase 8).
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Single audit log entry for API responses."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    action: str
    module: str
    resource_type: str | None
    target_id: str | None
    actor_id: uuid.UUID | None
    business_id: uuid.UUID | None
    before_value: dict[str, Any] | None
    after_value: dict[str, Any] | None
    payload: dict[str, Any] | None
    severity: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime.datetime
