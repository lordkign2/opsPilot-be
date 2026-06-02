"""
OpsPilot — Distributed WebSocket Broadcaster.

Leverages Redis Pub/Sub for cross-instance messaging to support horizontal scaling.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from app.core.logging import get_logger
from app.websocket.manager import ws_manager

logger = get_logger("websocket.broadcaster")


REDIS_CHANNEL = "opspilot:broadcast"
_subscriber_task: asyncio.Task[Any] | None = None


async def publish_event(
    business_id: str,
    event_type: str,
    payload: dict[str, Any],
    user_id: str | None = None,
) -> None:
    """
    Publish an event to the Redis Pub/Sub channel.
    This fans out to all active application nodes.
    """
    import redis.asyncio as aioredis

    from app.core.config import get_settings

    settings = get_settings()
    client = aioredis.from_url(
        settings.REDIS_URL.get_secret_value(),
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        message = {
            "business_id": business_id,
            "event_type": event_type,
            "payload": payload,
            "user_id": user_id,
        }
        await client.publish(REDIS_CHANNEL, json.dumps(message))
        logger.debug("Published event '%s' to Redis channel for business %s", event_type, business_id)
    except Exception as e:
        logger.error("Failed to publish event to Redis: %s", e, exc_info=True)
    finally:
        await client.close()


async def redis_subscriber_loop() -> None:
    """
    Background loop subscribing to Redis Pub/Sub channel and fanning out to local WebSockets.

    Features resilient automatic reconnection with exponential backoff to survive Redis service downtime.
    """
    import redis.asyncio as aioredis

    from app.core.config import get_settings

    settings = get_settings()
    retry_delay = 1.0
    max_retry_delay = 60.0
    backoff_factor = 2.0

    logger.info("Starting distributed WebSocket broadcaster subscriber loop...")

    while True:
        client = None
        pubsub = None
        try:
            client = aioredis.from_url(
                settings.REDIS_URL.get_secret_value(),
                encoding="utf-8",
                decode_responses=True,
            )
            pubsub = client.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL)
            logger.info("Successfully subscribed to Redis channel: %s", REDIS_CHANNEL)

            # Reset backoff delay upon successful connection
            retry_delay = 1.0

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    b_id = data.get("business_id")
                    event_type = data.get("event_type")
                    payload = data.get("payload", {})
                    u_id = data.get("user_id")

                    if not b_id or not event_type:
                        continue

                    # Fan out to local sockets via ws_manager
                    if u_id:
                        await ws_manager.broadcast_to_user(b_id, u_id, event_type, payload)
                    else:
                        await ws_manager.broadcast_to_business(b_id, event_type, payload)

                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON payload from Redis channel: %s", message["data"])
                except Exception as ex:
                    logger.error("Error routing Pub/Sub message to WebSockets: %s", ex, exc_info=True)

        except asyncio.CancelledError:
            logger.info("Redis subscriber loop task cancelled.")
            if pubsub:
                with contextlib.suppress(Exception):
                    await pubsub.unsubscribe(REDIS_CHANNEL)
                    await pubsub.close()
            if client:
                with contextlib.suppress(Exception):
                    await client.close()
            break

        except Exception as e:
            # Silence standard idle timeouts to keep logs clean
            is_timeout = "timeout" in str(e).lower()
            if is_timeout:
                logger.debug("Redis subscriber loop read timeout (idle connection).")
            else:
                logger.error(
                    "Redis subscriber loop disconnected or failed to connect: %s. Reconnecting in %.2fs...",
                    e,
                    retry_delay,
                    exc_info=True,
                )
            if pubsub:
                with contextlib.suppress(Exception):
                    await pubsub.close()
            if client:
                with contextlib.suppress(Exception):
                    await client.close()

            # Fast reconnect for timeouts, backoff for actual errors
            sleep_time = 0.1 if is_timeout else retry_delay
            await asyncio.sleep(sleep_time)
            if not is_timeout:
                retry_delay = min(retry_delay * backoff_factor, max_retry_delay)


def start_broadcaster() -> None:
    """Start the Redis subscriber loop in the background."""
    global _subscriber_task
    if _subscriber_task is None or _subscriber_task.done():
        _subscriber_task = asyncio.create_task(redis_subscriber_loop())
        logger.info("Distributed broadcaster task started in background.")


async def stop_broadcaster() -> None:
    """Stop the Redis subscriber task gracefully."""
    global _subscriber_task
    if _subscriber_task and not _subscriber_task.done():
        _subscriber_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _subscriber_task
        logger.info("Distributed broadcaster task stopped.")
