"""
OpsPilot — Rate Limiting Middleware (Phase 8).

Redis-backed sliding-window rate limiter using an atomic Lua script.
Falls back to the in-memory token-bucket approach when Redis is unavailable,
ensuring resilience in development and network-partitioned environments.

Redis key scheme: ``ratelimit:{bucket_key}``
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger
from app.core.metrics import background_jobs_total  # reuse existing Counter for rate-limit hits

logger = get_logger("middleware.rate_limit")

# Prometheus counter for rate-limit rejections
# (re-uses background_jobs_total with label job_name="rate_limit" as a lightweight solution;
#  a dedicated counter can be added to metrics.py if granularity is needed)

# ── Redis Lua Sliding Window Script ──────────────────────────
# Atomically:
#  1. Remove timestamps outside the current window.
#  2. Count remaining entries.
#  3. Reject if at/over the limit.
#  4. Otherwise append the current timestamp and set TTL.
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local cutoff = now - window

redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
if count >= limit then
    return 0
end
redis.call('ZADD', key, now, now .. '-' .. math.random(1, 1000000))
redis.call('EXPIRE', key, window)
return 1
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter per client IP (or per user once authenticated).

    Uses Redis for atomic, multi-instance-safe counting.
    Falls back to an in-memory token bucket if Redis is unreachable.

    Defaults:
      - 60 requests / 60 seconds for general endpoints.
      - 10 requests / 60 seconds for auth endpoints (login, register).
    """

    def __init__(
        self,
        app: Any,
        *,
        default_limit: int = 60,
        auth_limit: int = 10,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.default_limit = default_limit
        self.auth_limit = auth_limit
        self.window_seconds = window_seconds
        # Fallback in-memory buckets (used when Redis is unavailable)
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip health, metrics, and websocket endpoints
        if request.url.path in ("/health", "/healthz", "/", "/metrics", "/api/v1/ws"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        path = request.url.path
        is_auth = any(path.startswith(p) for p in ("/api/v1/auth/login", "/api/v1/auth/register"))
        limit = self.auth_limit if is_auth else self.default_limit
        bucket_key = f"{client_ip}:{path}" if is_auth else client_ip
        redis_key = f"ratelimit:{bucket_key}"

        allowed = await self._check_redis(redis_key, limit)

        if not allowed:
            logger.warning("Rate limit hit: %s (%s)", bucket_key, path)
            background_jobs_total.labels(job_name="rate_limit", status="rejected").inc()
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Too many requests. Please try again later.",
                    "error_code": "RATE_LIMIT",
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        return await call_next(request)

    async def _check_redis(self, key: str, limit: int) -> bool:
        """
        Run the sliding-window Lua script against Redis.
        Returns True (allowed) or False (rejected).
        Falls back to in-memory on Redis errors.
        """
        try:
            from typing import Any, cast

            from app.db.redis import redis_client

            now_ms = int(time.time() * 1000)
            result = await cast(Any, redis_client).eval(
                _SLIDING_WINDOW_LUA,
                1,
                key,
                now_ms,
                self.window_seconds * 1000,
                limit,
            )
            return bool(result)
        except Exception as exc:
            logger.debug("Redis rate-limit unavailable, using fallback: %s", exc)
            return self._check_memory(key, limit)

    def _check_memory(self, key: str, limit: int) -> bool:
        """In-memory sliding window fallback."""
        now = time.time()
        cutoff = now - self.window_seconds
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]
        if len(self._buckets[key]) >= limit:
            return False
        self._buckets[key].append(now)
        return True

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP, respecting proxy headers."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
