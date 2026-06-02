"""
OpsPilot — Sentry Error Tracking Integration (Phase 7).

Initialises Sentry SDK with FastAPI, SQLAlchemy, and Redis integrations.
This module is a complete no-op when SENTRY_DSN is not set, so local
development remains clean without any config changes.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("opspilot.sentry")


def init_sentry() -> None:
    """
    Initialise the Sentry SDK if SENTRY_DSN is configured.

    Call once during application startup (lifespan context).
    Safe to call multiple times — subsequent calls are no-ops when
    Sentry is already initialised.
    """
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.SENTRY_DSN:
        logger.debug("SENTRY_DSN not set — Sentry integration disabled.")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        dsn = settings.SENTRY_DSN.get_secret_value()
        environment = settings.SENTRY_ENVIRONMENT or settings.APP_ENV.value

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=f"opspilot@{settings.APP_VERSION}",
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[
                StarletteIntegration(transaction_style="url"),
                FastApiIntegration(transaction_style="url"),
                SqlalchemyIntegration(),
            ],
            # Strip PII from breadcrumbs
            send_default_pii=False,
        )

        logger.info(
            "Sentry initialised [env=%s, release=opspilot@%s, sample_rate=%.0f%%]",
            environment,
            settings.APP_VERSION,
            settings.SENTRY_TRACES_SAMPLE_RATE * 100,
        )

    except ImportError:
        logger.warning("sentry-sdk is not installed. Run `poetry add 'sentry-sdk[fastapi]'` to enable error tracking.")
    except Exception as exc:
        # Never let Sentry init crash the application
        logger.error("Failed to initialise Sentry: %s", exc)


def set_sentry_user(
    user_id: str | None = None,
    business_id: str | None = None,
    email: str | None = None,
) -> None:
    """
    Attach user context to the current Sentry scope.

    Call this after authentication succeeds inside route handlers
    to enrich error reports with user identity information.

    Usage::

        from app.core.sentry import set_sentry_user

        @router.get("/orders")
        async def list_orders(user: User = Depends(get_current_user)):
            set_sentry_user(
                user_id=str(user.id),
                business_id=str(user.business_id),
                email=user.email,
            )
            ...
    """
    try:
        import sentry_sdk

        with sentry_sdk.configure_scope() as scope:
            scope.set_user(
                {
                    k: v
                    for k, v in {
                        "id": user_id,
                        "business_id": business_id,
                        "email": email,
                    }.items()
                    if v is not None
                }
            )
    except Exception:
        # Sentry helpers must never raise
        pass
