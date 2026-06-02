"""
OpsPilot — Workflow Automation Module: Event Triggers & Redis Caching.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import Event, event_bus
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.modules.workflows.engine import evaluate_and_run_workflow
from app.modules.workflows.models import Workflow
from app.modules.workflows.repository import WorkflowRepository

logger = get_logger("workflows.triggers")

REDIS_CACHE_PREFIX = "opspilot:cache:workflows"
CACHE_EXPIRY_SECONDS = 86400  # Cache lives for 24 hours


def get_cache_key(business_id: uuid.UUID | str, trigger_type: str) -> str:
    """Helper to structure consistent Redis keys."""
    return f"{REDIS_CACHE_PREFIX}:{business_id}:{trigger_type}"


async def invalidate_workflow_cache(business_id: uuid.UUID | str, trigger_type: str) -> None:
    """
    Deletes the Redis cache entry for active business workflows.
    Should be triggered upon any rule CRUD mutations.
    """
    key = get_cache_key(business_id, trigger_type)
    try:
        import redis.asyncio as aioredis

        settings = get_settings()
        client = aioredis.from_url(
            settings.REDIS_URL.get_secret_value(),
            encoding="utf-8",
            decode_responses=True,
        )
        await client.delete(key)
        await client.close()
        logger.debug("Successfully invalidated workflow cache key '%s'", key)
    except Exception as e:
        logger.warning("Failed to invalidate Redis workflow cache key '%s': %s", key, e)


async def get_active_workflows_cached(
    db: AsyncSession, business_id: uuid.UUID, trigger_type: str
) -> list[dict[str, Any]]:
    """
    Resolves workflows for a merchant from Redis cache first.
    Falls back to PostgreSQL and updates cache on miss.
    """
    key = get_cache_key(business_id, trigger_type)
    redis_available = False
    cached_data = None

    import redis.asyncio as aioredis

    settings = get_settings()
    client = aioredis.from_url(
        settings.REDIS_URL.get_secret_value(),
        encoding="utf-8",
        decode_responses=True,
    )

    try:
        cached_data = await client.get(key)
        redis_available = True
    except Exception as e:
        logger.warning("Redis temporary lookup failure on key '%s': %s. Falling back to DB.", key, e)

    # 1. Cache hit
    if cached_data:
        try:
            logger.debug("Workflow cache hit for key '%s'", key)
            await client.close()
            return cast(list[dict[str, Any]], json.loads(cached_data))
        except Exception:
            pass

    # 2. Cache miss or Redis down: Fetch from database
    logger.debug("Workflow cache miss for key '%s' (fetching from Postgres)", key)
    repo = WorkflowRepository(db)
    workflows = await repo.get_active_by_trigger(business_id, trigger_type)

    # Transform objects into dict arrays for serialization
    workflows_serialized = []
    for w in workflows:
        workflows_serialized.append(
            {
                "id": str(w.id),
                "business_id": str(w.business_id),
                "name": w.name,
                "description": w.description,
                "trigger_type": w.trigger_type,
                "is_active": w.is_active,
                "conditions": w.conditions,
                "actions": w.actions,
                "log_depth": w.log_depth,
            }
        )

    # Save to Redis for next hits (if Redis is operational)
    if redis_available:
        try:
            await client.setex(key, CACHE_EXPIRY_SECONDS, json.dumps(workflows_serialized))
            logger.debug("Successfully populated workflow cache for key '%s'", key)
        except Exception as ex:
            logger.warning("Failed to write to Redis cache key '%s': %s", key, ex)

    await client.close()
    return workflows_serialized


async def handle_system_workflow_trigger(event: Event) -> None:
    """
    Decoupled trigger listener. Subscribes to event_bus events.
    Spawns out-of-band evaluation runs in the background.
    """
    payload = event.payload
    business_id_str = payload.get("business_id")
    if not business_id_str:
        return

    try:
        business_id = uuid.UUID(str(business_id_str))
    except ValueError:
        return

    # Spawn fresh session and background task
    async def process_trigger() -> None:
        async with async_session_factory() as db:
            try:
                # 1. Fetch active rules (uses high-performance cache)
                rules = await get_active_workflows_cached(db, business_id, event.event_type)
                if not rules:
                    return

                # 2. Process each rule concurrently
                from app.core.config import get_settings

                is_testing = get_settings().is_testing

                for rule_dict in rules:
                    # Construct model instance mapping
                    w = Workflow(
                        id=uuid.UUID(rule_dict["id"]),
                        business_id=uuid.UUID(rule_dict["business_id"]),
                        name=rule_dict["name"],
                        description=rule_dict["description"],
                        trigger_type=rule_dict["trigger_type"],
                        is_active=rule_dict["is_active"],
                        conditions=rule_dict["conditions"],
                        actions=rule_dict["actions"],
                        log_depth=rule_dict["log_depth"],
                    )
                    # Await synchronously in testing mode to protect transaction boundaries
                    if is_testing:
                        await evaluate_and_run_workflow(db, w, payload)
                    else:
                        asyncio.create_task(evaluate_and_run_workflow(db, w, payload))
            except Exception as ex:
                logger.error("Error in background workflows trigger resolver: %s", ex, exc_info=True)

    # Dispatch either synchronously (for test reliability) or asynchronously (for production scalability)
    from app.core.config import get_settings

    if get_settings().is_testing:
        await process_trigger()
    else:
        asyncio.create_task(process_trigger())


# Standard automation events we support triggers for
AUTOMATION_TRIGGERS = [
    "order.created",
    "order.updated",
    "payment.success",
    "payment.failed",
    "customer.inactive",
]


def register_workflow_trigger_listeners() -> None:
    """Bridges system event_bus events into our automation routing hooks."""
    for event_type in AUTOMATION_TRIGGERS:
        event_bus.subscribe(event_type, handle_system_workflow_trigger)
        logger.debug("Bound workflow engine triggers to system event '%s'", event_type)
