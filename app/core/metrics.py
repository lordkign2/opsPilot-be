"""
OpsPilot — Prometheus Metrics Registry (Phase 7).

Single source-of-truth for all custom Prometheus metrics.
HTTP metrics are handled automatically by prometheus-fastapi-instrumentator.
This module adds domain-specific gauges and counters for:
  - Active WebSocket connections
  - Event bus emissions and handler failures
  - Background job completion tracking
  - Workflow execution outcomes
  - Webhook retry tracking
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge

# ── WebSocket ────────────────────────────────────────────────

active_ws_connections: Gauge = Gauge(
    "opspilot_active_ws_connections",
    "Number of currently active WebSocket connections across all business workspaces.",
    labelnames=["business_id"],
)

# ── Event Bus ────────────────────────────────────────────────

event_bus_emissions_total: Counter = Counter(
    "opspilot_event_bus_emissions_total",
    "Total number of events emitted on the internal event bus.",
    labelnames=["event_type"],
)

event_bus_handler_failures_total: Counter = Counter(
    "opspilot_event_bus_handler_failures_total",
    "Total number of event handler failures on the internal event bus.",
    labelnames=["event_type"],
)

# ── Background Jobs ──────────────────────────────────────────

background_jobs_total: Counter = Counter(
    "opspilot_background_jobs_total",
    "Total background job executions, labelled by job name and outcome.",
    labelnames=["job_name", "status"],
)

# ── Workflow Engine ──────────────────────────────────────────

workflow_executions_total: Counter = Counter(
    "opspilot_workflow_executions_total",
    "Total workflow execution attempts, labelled by outcome (success, failed, skipped).",
    labelnames=["status"],
)

# ── Webhook Retries ──────────────────────────────────────────

webhook_retries_total: Counter = Counter(
    "opspilot_webhook_retries_total",
    "Total webhook delivery retries, labelled by integration provider.",
    labelnames=["provider"],
)
