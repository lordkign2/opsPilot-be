"""
OpsPilot — API Keys Module: Repository (Phase 8).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.api_keys.models import APIKey


class APIKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, key: APIKey) -> APIKey:
        self.db.add(key)
        await self.db.flush()
        return key

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        """Lookup an active key by its SHA-256 hash."""
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_business(self, business_id: uuid.UUID) -> list[APIKey]:
        result = await self.db.execute(
            select(APIKey).where(APIKey.business_id == business_id).order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, key_id: uuid.UUID, business_id: uuid.UUID) -> bool:
        """Soft-revoke a key (sets is_active=False). Returns True if the key was found."""
        result = await self.db.execute(
            update(APIKey).where(APIKey.id == key_id, APIKey.business_id == business_id).values(is_active=False)
        )
        await self.db.flush()
        return (result.rowcount or 0) > 0  # type: ignore[attr-defined]

    async def touch(self, key_id: uuid.UUID) -> None:
        """Update last_used_at to now."""
        from datetime import datetime, timezone

        await self.db.execute(update(APIKey).where(APIKey.id == key_id).values(last_used_at=datetime.now(timezone.utc)))
        await self.db.flush()
