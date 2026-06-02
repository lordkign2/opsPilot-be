"""
OpsPilot — Request Logging Middleware.

Logs every request/response with method, path, status code,
and duration. Uses the structured logger with request ID.
In production, emits structured JSON fields for Loki/Grafana ingestion.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("middleware.logging")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming requests and outgoing responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()

        # Skip health check noise
        if request.url.path in ("/health", "/healthz", "/", "/metrics"):
            return await call_next(request)

        logger.info(
            "%s %s started",
            request.method,
            request.url.path,
        )

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "http_status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return response
