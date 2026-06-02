"""
OpsPilot — Centralised Router Registry.

All module routers are registered here. Adding a new module
is a one-line change in this file — main.py never needs to
be touched again.

At 100+ endpoints across 8+ modules, this prevents main.py
from becoming a sprawling import dump.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

# ── API v1 Master Router ────────────────────────────────────
api_v1_router = APIRouter(prefix="/api/v1")


def register_routers(app: FastAPI) -> None:
    """
    Import and mount all module routers onto the v1 prefix.

    To add a new module:
    1. Create `app/modules/<name>/routes.py` with a `router` object.
    2. Add one import + one `include_router` line here.
    """

    # ── Auth ─────────────────────────────────────────────────
    from app.modules.auth.routes import router as auth_router

    api_v1_router.include_router(auth_router)

    # ── Businesses ───────────────────────────────────────────
    from app.modules.businesses.routes import router as businesses_router

    api_v1_router.include_router(businesses_router)

    # ── Customers ────────────────────────────────────────────
    from app.modules.customers.routes import router as customers_router

    api_v1_router.include_router(customers_router)

    # ── Orders ───────────────────────────────────────────────
    from app.modules.orders.routes import router as orders_router

    api_v1_router.include_router(orders_router)

    # ── Payments ─────────────────────────────────────────────
    from app.modules.payments.routes import router as payments_router

    api_v1_router.include_router(payments_router)

    # ── Phase 3 Modules ──────────────────────────────────────
    from app.modules.ai.routes import router as ai_router

    api_v1_router.include_router(ai_router)

    from app.modules.analytics.routes import router as analytics_router

    api_v1_router.include_router(analytics_router)

    from app.modules.notifications.routes import router as notifications_router

    api_v1_router.include_router(notifications_router)

    # ── WebSocket Gateway (Phase 4) ──────────────────────────
    from app.websocket.routes import router as ws_router

    api_v1_router.include_router(ws_router)

    # ── Workflows Gateway (Phase 5) ──────────────────────────
    from app.modules.workflows.routes import router as workflows_router

    api_v1_router.include_router(workflows_router)

    # ── Integrations (Phase 6) ───────────────────────────────
    from app.integrations.payments.flutterwave import router as flutterwave_router
    from app.integrations.payments.paystack import router as paystack_router
    from app.integrations.whatsapp.webhook import router as whatsapp_router

    api_v1_router.include_router(whatsapp_router)
    api_v1_router.include_router(paystack_router)
    api_v1_router.include_router(flutterwave_router)

    # ── Super-Admin Ops (Phase 7) ────────────────────────────
    from app.modules.admin.routes import router as admin_router

    api_v1_router.include_router(admin_router)

    # ── Security & Auditing (Phase 8) ──────────────────────────
    from app.modules.api_keys.routes import router as api_keys_router
    from app.modules.audit.routes import router as audit_router

    api_v1_router.include_router(api_keys_router)
    api_v1_router.include_router(audit_router)

    # ── Mount the v1 router onto the app ─────────────────────
    app.include_router(api_v1_router)


def register_event_handlers() -> None:
    """
    Import all event handler modules so they register
    their listeners on the event bus at startup.

    Adding a module? Import its events module here.
    """
    import app.modules.audit.events  # noqa: F401
    import app.modules.auth.events  # noqa: F401
    import app.modules.businesses.events  # noqa: F401
    import app.modules.customers.events  # noqa: F401
    import app.modules.notifications.events  # noqa: F401
    import app.modules.orders.events  # noqa: F401
    import app.modules.payments.events  # noqa: F401

    # Register real-time event bridge (Phase 4)
    from app.websocket.events import register_ws_event_bridge

    register_ws_event_bridge()

    # Register workflow trigger listeners (Phase 5)
    from app.modules.workflows.triggers import register_workflow_trigger_listeners

    register_workflow_trigger_listeners()
