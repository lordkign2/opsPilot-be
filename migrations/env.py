"""
Alembic Environment Configuration.

Reads the database URL from app settings (not alembic.ini)
and configures async migrations with the project's ORM models.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base
from app.modules.ai.models import AILog, AIMemory, PromptTemplate  # noqa: F401
from app.modules.audit.models import AuditLog  # noqa: F401

# Import ALL models so Alembic sees them for autogeneration
from app.modules.auth.models import User  # noqa: F401
from app.modules.billing.models import Invoice, Subscription  # noqa: F401
from app.modules.businesses.models import Business  # noqa: F401
from app.modules.customers.models import Customer  # noqa: F401
from app.modules.feature_flags.models import BusinessFeatureFlag, FeatureFlag, SubscriptionTier  # noqa: F401
from app.modules.metering.models import UsageMeter  # noqa: F401
from app.modules.notifications.models import Notification  # noqa: F401
from app.modules.orders.models import Order  # noqa: F401
from app.modules.payments.models import Payment  # noqa: F401
from app.modules.workflows.models import Workflow, WorkflowExecutionLog  # noqa: F401

# ── Alembic Config ───────────────────────────────────────────
config = context.config
settings = get_settings()

# Override sqlalchemy.url from application settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.get_secret_value())

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without connecting."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations with an active connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
