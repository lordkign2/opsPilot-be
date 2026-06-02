"""
OpsPilot — Redis Client.

Async Redis connection for token blacklisting, caching,
and future pub/sub.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

redis_client = aioredis.from_url(
    settings.REDIS_URL.get_secret_value(),
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency returning the Redis client."""
    return redis_client
