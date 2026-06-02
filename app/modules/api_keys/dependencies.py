"""
OpsPilot — API Keys Module: FastAPI Dependencies (Phase 8).

Provides ``authenticate_api_key()`` used by ``get_current_principal()``
in ``auth/dependencies.py`` to resolve a User from an ``X-API-Key`` header.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.modules.api_keys.models import APIKey
from app.modules.auth.models import User


async def authenticate_api_key(api_key: str, db: AsyncSession) -> User:
    """
    Validate an API key from the ``X-API-Key`` header and return the owning User.

    Steps:
    1. Hash the raw key value.
    2. Look up the active APIKey record by hash.
    3. Verify it hasn't expired.
    4. Load and return the owning business User (the ``created_by`` user).
    5. Fire-and-forget update of ``last_used_at`` (best-effort).

    Raises:
        UnauthorizedError: If the key is missing, invalid, expired, or revoked.
    """
    if not api_key or not api_key.startswith("opk_"):
        raise UnauthorizedError("Invalid API key format.")

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Lookup key
    result = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active.is_(True)))
    record = result.scalar_one_or_none()

    if record is None:
        raise UnauthorizedError("API key not found or revoked.")

    # Check expiry
    if record.expires_at is not None:
        from datetime import datetime, timezone

        if datetime.now(timezone.utc) > record.expires_at:
            raise UnauthorizedError("API key has expired.")

    # Load the owning user (the user who created the key acts as the principal)
    user_result = await db.execute(select(User).where(User.id == record.created_by, User.is_active.is_(True)))
    user = user_result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("API key owner account not found or deactivated.")

    # Best-effort last_used_at update (don't let this break auth)
    try:
        from datetime import datetime, timezone

        from sqlalchemy import update

        await db.execute(update(APIKey).where(APIKey.id == record.id).values(last_used_at=datetime.now(timezone.utc)))
        await db.commit()
    except Exception:
        pass

    return user
