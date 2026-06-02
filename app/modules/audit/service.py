"""
OpsPilot — Audit Module: Service (Phase 8).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_action(
        self,
        action: str,
        module: str,
        actor_id: str | None = None,
        business_id: str | None = None,
        target_id: str | None = None,
        resource_type: str | None = None,
        before_value: dict[str, Any] | None = None,
        after_value: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        severity: str = "info",
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Record an immutable audit event with before/after snapshots."""
        log_entry = AuditLog(
            action=action,
            module=module,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            business_id=uuid.UUID(business_id) if business_id else None,
            target_id=target_id,
            resource_type=resource_type,
            before_value=before_value,
            after_value=after_value,
            payload=payload,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log_entry)
        await self.db.commit()
        return log_entry

    async def get_logs(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Retrieve global audit logs (super-admin view)."""
        from sqlalchemy import func, select

        count_query = select(func.count()).select_from(AuditLog)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        logs = list(result.scalars().all())
        return logs, total

    async def get_logs_by_business(
        self,
        business_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Retrieve audit logs scoped to a specific business (owner view)."""
        from sqlalchemy import func, select

        count_query = select(func.count()).select_from(AuditLog).where(AuditLog.business_id == business_id)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = (
            select(AuditLog)
            .where(AuditLog.business_id == business_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        logs = list(result.scalars().all())
        return logs, total
