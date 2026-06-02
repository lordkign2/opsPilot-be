"""
OpsPilot — Internal Event Bus.

A lightweight in-process event system for decoupled module
communication. Modules publish events; other modules subscribe
to react without tight coupling.

In future phases, this can be extended to push events to
Redis Pub/Sub or a message broker for distributed processing.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.metrics import event_bus_emissions_total, event_bus_handler_failures_total

logger = logging.getLogger("opspilot.events")

# Type alias for async event handlers
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


@dataclass
class Event:
    """Base event structure."""

    event_type: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_module: str = ""


class EventBus:
    """
    Simple async event bus.

    Usage:
        bus = EventBus()

        @bus.on("order.created")
        async def handle_order_created(event: Event):
            ...

        await bus.emit("order.created", {"order_id": "..."})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event_type: str) -> Callable[[EventHandler], EventHandler]:
        """Decorator to register an event handler."""

        def decorator(handler: EventHandler) -> EventHandler:
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                logger.debug(
                    "Registered handler %s for event '%s'",
                    handler.__name__,
                    event_type,
                )
            return handler

        return decorator

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Programmatically subscribe a handler to an event type."""
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        source_module: str = "",
    ) -> None:
        """
        Emit an event to all registered handlers.

        Handlers run concurrently via asyncio.gather.
        Exceptions in one handler don't block others.
        """
        event = Event(
            event_type=event_type,
            payload=payload or {},
            source_module=source_module,
        )

        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.debug("No handlers for event '%s'", event_type)
            return

        # Track every emission regardless of handler count
        event_bus_emissions_total.labels(event_type=event_type).inc()

        logger.info(
            "Emitting '%s' to %d handler(s) [id=%s]",
            event_type,
            len(handlers),
            event.event_id,
        )

        from app.core.config import get_settings

        results: list[Any] = []
        if get_settings().is_testing:
            # Execute handlers sequentially in testing mode to prevent concurrent database session access
            for handler in handlers:
                try:
                    await handler(event)
                    results.append(None)
                except Exception as ex:
                    results.append(ex)
        else:
            # Execute handlers concurrently in production/development
            results = list(
                await asyncio.gather(
                    *(handler(event) for handler in handlers),
                    return_exceptions=True,
                )
            )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                event_bus_handler_failures_total.labels(event_type=event_type).inc()
                logger.error(
                    "Handler %s failed for event '%s': %s",
                    handlers[i].__name__,
                    event_type,
                    result,
                    exc_info=result,
                )


# ── Singleton ────────────────────────────────────────────────
event_bus = EventBus()
