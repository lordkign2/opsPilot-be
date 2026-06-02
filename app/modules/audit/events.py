"""
OpsPilot — Audit Module: Event Listeners (Phase 8).

Subscribes to critical system events and writes enterprise-grade audit
log entries capturing who, what, when, and before/after snapshots.
"""

from app.core.events import Event, event_bus
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.modules.audit.service import AuditService

logger = get_logger("audit.events")


async def _record(event: Event, *, resource_type: str, severity: str = "info") -> None:
    """Helper: open a DB session and write one audit log entry."""
    async with async_session_factory() as db:
        svc = AuditService(db)
        await svc.log_action(
            action=event.event_type,
            module=event.source_module or resource_type,
            actor_id=event.payload.get("user_id") or event.payload.get("actor_id"),
            business_id=event.payload.get("business_id"),
            target_id=str(event.payload.get("id") or event.payload.get("order_id") or ""),
            resource_type=resource_type,
            before_value=event.payload.get("before"),
            after_value=event.payload.get("after"),
            payload={k: v for k, v in event.payload.items() if k not in ("before", "after")},
            severity=severity,
        )
        logger.debug("Audit recorded: %s [%s]", event.event_type, resource_type)


# ── Auth Events ──────────────────────────────────────────────


@event_bus.on("user.registered")
async def on_user_registered(event: Event) -> None:
    await _record(event, resource_type="user", severity="info")


@event_bus.on("user.logged_in")
async def on_user_logged_in(event: Event) -> None:
    await _record(event, resource_type="user", severity="info")


# ── Order Events ─────────────────────────────────────────────


@event_bus.on("order.created")
async def on_order_created(event: Event) -> None:
    await _record(event, resource_type="order", severity="info")


@event_bus.on("order.updated")
async def on_order_updated(event: Event) -> None:
    await _record(event, resource_type="order", severity="info")


# ── Payment Events ───────────────────────────────────────────


@event_bus.on("payment.success")
async def on_payment_success(event: Event) -> None:
    await _record(event, resource_type="payment", severity="info")


@event_bus.on("payment.failed")
async def on_payment_failed(event: Event) -> None:
    await _record(event, resource_type="payment", severity="warning")
