"""
OpsPilot — Application Entry Point.

Wires together all modules, middleware, and lifecycle events
into a single FastAPI application instance.

This file should rarely need editing. New modules are added
via `app/core/registry.py` — not here.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import get_settings
from app.core.exceptions import OpsPilotException
from app.core.logging import get_logger, setup_logging
from app.core.registry import register_event_handlers, register_routers
from app.core.sentry import init_sentry
from app.middleware.cors import add_cors_middleware
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.maintenance import MaintenanceModeMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.shared.response import error_response

settings = get_settings()
logger = get_logger("main")


# ── Lifecycle ────────────────────────────────────────────────


async def seed_super_admin() -> None:
    """Ensure the original master super-admin is seeded in the database."""
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import async_session_factory
    from app.modules.auth.models import User, UserRole

    email = settings.SUPER_ADMIN_EMAIL
    password = settings.SUPER_ADMIN_PASSWORD.get_secret_value()

    async with async_session_factory() as session:
        try:
            result = await session.execute(select(User).where(User.email == email))
            admin = result.scalar_one_or_none()
            if not admin:
                logger.info("Original super-admin not found, seeding...")
                hashed = hash_password(password)
                new_admin = User(
                    email=email,
                    password_hash=hashed,
                    first_name="Original",
                    last_name="Super Admin",
                    role=UserRole.SUPER_ADMIN,
                    business_id=None,
                    is_active=True,
                    is_verified=True,
                )
                session.add(new_admin)
                await session.commit()
                logger.info("Original super-admin seeded successfully.")
            else:
                logger.info("Original super-admin already exists.")
        except Exception as e:
            logger.error("Failed to seed super-admin: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown hooks."""
    setup_logging()

    # Initialise Sentry error tracking (Phase 7) — no-op if SENTRY_DSN is unset
    init_sentry()

    register_event_handlers()

    # Start horizontal broadcaster for WebSockets (Phase 4)
    from app.websocket.broadcaster import start_broadcaster

    start_broadcaster()

    # Expose Prometheus /metrics endpoint (Phase 7) — instrumented at module-level
    # (routes and middleware must be registered before startup)

    # Seed the original super-admin
    await seed_super_admin()

    logger.info(
        "Starting %s v%s [%s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV.value,
    )

    # Setup fastapi-cache2
    from typing import Any, cast

    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.redis import RedisBackend

    from app.db.redis import redis_client

    FastAPICache.init(RedisBackend(cast(Any, redis_client)), prefix="opspilot-cache")

    yield

    # Shutdown
    from app.db.redis import redis_client
    from app.db.session import engine
    from app.websocket.broadcaster import stop_broadcaster

    await stop_broadcaster()
    await engine.dispose()
    with suppress(RuntimeError):
        await redis_client.aclose()
    logger.info("Shutdown complete.")


# ── Application ──────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered business operations platform for SMEs",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)


# ── Middleware (outermost → innermost) ───────────────────────

add_cors_middleware(app)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(MaintenanceModeMiddleware)
app.add_middleware(RateLimitMiddleware, default_limit=60, auth_limit=10)


# ── Global Exception Handlers ───────────────────────────────


@app.exception_handler(OpsPilotException)
async def opspilot_exception_handler(request: Request, exc: OpsPilotException) -> JSONResponse:
    """Convert custom exceptions into standardised JSON errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=exc.detail,
            error_code=exc.error_code,
            details=exc.context if exc.context else None,
        ),
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content=error_response(
            message="An unexpected error occurred.",
            error_code="INTERNAL_ERROR",
        ),
    )


# ── Register All Module Routers ──────────────────────────────

register_routers(app)


# ── Prometheus Metrics (Phase 7) ─────────────────────────────
# Must be registered at module level (before app starts) so that
# `.instrument()` can add its middleware and `.expose()` can add
# the /metrics route — both operations are forbidden post-startup.

if settings.PROMETHEUS_ENABLED:
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health", "/healthz", "/"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# ── Health Check ─────────────────────────────────────────────


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV.value,
    }


@app.get("/", tags=["Health"])
async def root() -> dict[str, Any]:
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.is_development else None,
    }
