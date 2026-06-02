"""
OpsPilot — Structured Logging.

JSON-formatted logging with correlation IDs for request tracing.
"""

from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from uuid import uuid4

from app.core.config import get_settings

# ── Context Variables (set per-request/session by middleware/auth) ──
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
business_id_ctx: ContextVar[str | None] = ContextVar("business_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


class StructuredFormatter(logging.Formatter):
    """
    Produces enterprise-grade structured log lines.
    In production, outputs a single-line JSON string containing all core variables
    plus any dynamic context passed via `extra=...`.
    In development, outputs cleanly aligned human-readable tracing logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Injects global context variables
        record.request_id = request_id_ctx.get() or "-"
        record.business_id = business_id_ctx.get() or "-"
        record.user_id = user_id_ctx.get() or "-"
        record.trace_id = trace_id_ctx.get() or "-"
        record.module_name = record.name

        settings = get_settings()
        if settings.is_production:
            import orjson

            log_data = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "request_id": getattr(record, "request_id", "-"),
                "business_id": getattr(record, "business_id", "-"),
                "user_id": getattr(record, "user_id", "-"),
                "trace_id": getattr(record, "trace_id", "-"),
            }
            if record.exc_info and record.exc_info[1]:
                log_data["exception"] = self.formatException(record.exc_info)

            # Auto-extract and serialize any dynamic context passed via logger.info("...", extra={...})
            standard_attrs = {
                "args",
                "asctime",
                "created",
                "exc_info",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "request_id",
                "business_id",
                "user_id",
                "trace_id",
                "module_name",
            }
            for key, val in record.__dict__.items():
                if key not in standard_attrs and not key.startswith("_"):
                    log_data[key] = val

            return orjson.dumps(log_data).decode()
        else:
            # Clean development console alignment including tenancy tags
            req_id = getattr(record, "request_id", "-")
            b_id = getattr(record, "business_id", "-")
            u_id = getattr(record, "user_id", "-")
            return (
                f"{self.formatTime(record)} | {record.levelname:<8} | "
                f"{req_id} | b:{b_id:<36} | u:{u_id:<36} | "
                f"{record.name} | {record.getMessage()}"
            )


def setup_logging() -> None:
    """Configure application logging."""
    settings = get_settings()
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # File Logging: Rotated log file to separate physical logging from Swagger
    try:
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/opspilot.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(StructuredFormatter())
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Fallback if logs directory cannot be written to
        sys.stderr.write(f"Failed to initialize file logger: {e}\n")

    # Quieten noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if settings.DATABASE_ECHO else logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Use module __name__ as the name."""
    return logging.getLogger(f"opspilot.{name}")


def get_trace_id() -> str:
    """
    Return the current trace ID, or generate and bind a new one.

    Call this in background tasks and async workers to ensure
    every log line within the task carries a stable trace_id.

    Usage::

        from app.core.logging import get_trace_id, trace_id_ctx

        async def my_background_task() -> None:
            trace_id_ctx.set(get_trace_id())
            logger.info("task started")
    """
    tid = trace_id_ctx.get()
    if tid is None:
        tid = str(uuid4())
        trace_id_ctx.set(tid)
    return tid
