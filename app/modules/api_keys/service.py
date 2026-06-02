"""
OpsPilot — API Keys Module: Service (Phase 8).

Handles secure API key generation and management.

Security design:
  - Keys use the ``opk_`` prefix for easy identification.
  - Only the SHA-256 hex digest of the raw key is stored.
  - The raw key is returned exactly once on creation and never again.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.api_keys.models import APIKey
from app.modules.api_keys.repository import APIKeyRepository
from app.modules.api_keys.schemas import APIKeyCreate, APIKeyCreatedResponse, APIKeyResponse

_KEY_PREFIX = "opk_"
_KEY_RANDOM_BYTES = 30  # generates ~40 URL-safe base64 chars → total key ≈ 44 chars


class APIKeyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = APIKeyRepository(db)

    @staticmethod
    def _generate_raw_key() -> str:
        """Generate a secure random key with the `opk_` prefix."""
        return _KEY_PREFIX + secrets.token_urlsafe(_KEY_RANDOM_BYTES)

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        """SHA-256 hex digest of the raw key (used for storage and lookup)."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    async def create_key(
        self,
        payload: APIKeyCreate,
        business_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> APIKeyCreatedResponse:
        """
        Generate a new API key and store only its hash.

        Returns :class:`APIKeyCreatedResponse` containing the raw key — this
        is the **only time** the raw key is accessible.
        """
        raw_key = self._generate_raw_key()
        key_hash = self._hash_key(raw_key)
        key_hint = raw_key[-4:]  # last 4 chars for display

        key = APIKey(
            name=payload.name,
            description=payload.description,
            key_prefix=_KEY_PREFIX,
            key_hash=key_hash,
            key_hint=key_hint,
            business_id=business_id,
            created_by=created_by,
            expires_at=payload.expires_at,
        )
        created = await self.repo.create(key)
        await self.db.commit()

        return APIKeyCreatedResponse(
            id=created.id,
            name=created.name,
            description=created.description,
            key_hint=created.key_hint,
            key_prefix=created.key_prefix,
            is_active=created.is_active,
            last_used_at=created.last_used_at,
            expires_at=created.expires_at,
            created_at=created.created_at,
            raw_key=raw_key,
        )

    async def list_keys(self, business_id: uuid.UUID) -> list[APIKeyResponse]:
        """List all API keys for a business (metadata only — no raw keys)."""
        keys = await self.repo.list_by_business(business_id)
        return [APIKeyResponse.model_validate(k) for k in keys]

    async def revoke_key(self, key_id: uuid.UUID, business_id: uuid.UUID) -> None:
        """Revoke an API key by ID. Raises NotFoundError if not found."""
        found = await self.repo.revoke(key_id, business_id)
        if not found:
            raise NotFoundError("API key not found or already revoked.")
        await self.db.commit()
