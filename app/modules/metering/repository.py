import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.metering.models import UsageMeter


class UsageMeterRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_current_meter(
        self, business_id: uuid.UUID, metric_name: str, current_time: datetime | None = None
    ) -> UsageMeter | None:
        """Fetch the active meter for the given cycle."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(UsageMeter).where(
                UsageMeter.business_id == business_id,
                UsageMeter.metric_name == metric_name,
                UsageMeter.cycle_start_date <= current_time,
                UsageMeter.cycle_end_date >= current_time,
            )
        )
        return result.scalar_one_or_none()

    async def increment_usage(
        self, business_id: uuid.UUID, metric_name: str, amount: int, cycle_start: datetime, cycle_end: datetime
    ) -> UsageMeter:
        """
        Atomically increment usage using an upsert (INSERT ON CONFLICT DO UPDATE).
        Creates the meter if it doesn't exist for the cycle.
        """
        stmt = insert(UsageMeter).values(
            business_id=business_id,
            metric_name=metric_name,
            cycle_start_date=cycle_start,
            cycle_end_date=cycle_end,
            current_usage=amount,
        )

        # On conflict (meaning the meter for this cycle already exists), add the amount to current_usage
        stmt_returning = stmt.on_conflict_do_update(
            constraint="uq_business_metric_cycle", set_={"current_usage": UsageMeter.current_usage + amount}
        ).returning(UsageMeter)

        result = await self.db.execute(stmt_returning)
        await self.db.flush()
        return result.scalar_one()
