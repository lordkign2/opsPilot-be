import calendar
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.modules.metering.repository import UsageMeterRepository

# Define some basic hard limits for Phase 10 (without a full DB limits table yet)
TIER_LIMITS = {
    "free": {"ai_tokens": 10000, "workflow_executions": 50},
    "pro": {"ai_tokens": 100000, "workflow_executions": 500},
    "enterprise": {"ai_tokens": 1000000, "workflow_executions": 5000},
}


class MeteringService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UsageMeterRepository(db)

    def _get_current_cycle(self) -> tuple[datetime, datetime]:
        """Simple monthly billing cycle: 1st of month to end of month."""
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(now.year, now.month)[1]
        end = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
        return start, end

    async def _get_business_tier(self, business_id: uuid.UUID) -> str:
        # Mock logic. We should fetch this from the actual subscriptions table once integrated.
        from sqlalchemy import text

        result = await self.db.execute(
            text("SELECT tier_id FROM subscriptions WHERE business_id = :bid AND status = 'active'"),
            {"bid": business_id},
        )
        row = result.fetchone()
        return row[0] if row else "free"

    async def check_usage_limit(self, business_id: uuid.UUID, metric_name: str, check_amount: int = 1) -> None:
        """
        Check if adding `check_amount` to the current usage would exceed the tier limits.
        Raises ForbiddenError if limit exceeded.
        """
        tier = await self._get_business_tier(business_id)
        limit = TIER_LIMITS.get(tier, {}).get(metric_name)

        if limit is None:
            return  # No limit defined

        meter = await self.repo.get_current_meter(business_id, metric_name)
        current = meter.current_usage if meter else 0

        if current + check_amount > limit:
            raise ForbiddenError(f"Usage limit exceeded for {metric_name}. Upgrade your plan.")

    async def increment_usage(self, business_id: uuid.UUID, metric_name: str, amount: int = 1) -> None:
        """Increment the usage. Fire and forget."""
        start, end = self._get_current_cycle()
        await self.repo.increment_usage(business_id, metric_name, amount, start, end)
        await self.db.commit()


# Helper to trigger asynchronously from other endpoints
def background_increment_usage(db: AsyncSession, business_id: uuid.UUID, metric_name: str, amount: int = 1) -> None:
    """Helper to be used with FastAPI BackgroundTasks (requires a new DB session usually, but we assume it's safe if handled correctly)."""
    # Note: FastApi BackgroundTasks require their own db session if run after response,
    # so typically we would resolve it there or just await it before returning.
    pass
