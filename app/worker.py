"""
OpsPilot — ARQ Worker Configuration.

This file defines the worker class and settings for the `arq`
asynchronous task queue.
"""

from __future__ import annotations

import logging
from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.tasks.ai_tasks import generate_ai_insight_task
from app.core.tasks.billing_tasks import process_paystack_webhook_task

logger = logging.getLogger("opspilot.worker")
settings = get_settings()

# We need to construct RedisSettings from our REDIS_URL
# REDIS_URL usually looks like "redis://localhost:6379/0"
# For arq, we parse it or pass it safely.


async def startup(ctx: dict[str, Any]) -> None:
    """Run on worker startup."""
    logger.info("Starting OpsPilot ARQ worker...")
    # Initialize DB pools or other global state here if needed
    # ctx['db'] = ...


async def shutdown(ctx: dict[str, Any]) -> None:
    """Run on worker shutdown."""
    logger.info("Shutting down OpsPilot ARQ worker...")


class WorkerSettings:
    """
    Configuration for the ARQ worker.
    To run: `arq app.worker.WorkerSettings`
    """

    # In production, parse actual host/port/db from settings.REDIS_URL
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL.get_secret_value())

    functions = [
        generate_ai_insight_task,
        process_paystack_webhook_task,
    ]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 20
    job_timeout = 600  # 10 minutes max per job
