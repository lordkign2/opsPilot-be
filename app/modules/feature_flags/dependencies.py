from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_business_id
from app.modules.feature_flags.repository import FeatureFlagRepository


def require_feature(flag_id: str) -> Callable[..., Awaitable[uuid.UUID]]:
    """
    FastAPI Dependency to check if a feature flag is enabled for the business.
    This also needs to check the business's current subscription tier.
    For Phase 10, we will assume a base tier check if not fully implemented in billing yet.
    """

    async def feature_checker(
        business_id: uuid.UUID = Depends(get_current_business_id),
        db: AsyncSession = Depends(get_db),
    ) -> uuid.UUID:
        # In a real app, you'd fetch the business's current tier from the billing module here.
        # We will mock the current_tier_id to "free" for now, until billing models are queried.

        # To avoid circular imports if billing isn't ready yet:
        current_tier_id = "free"

        # We can implement an actual lookup if billing is ready:
        from sqlalchemy import text

        # Fast raw query to get subscription tier if it exists
        result = await db.execute(
            text("SELECT tier_id FROM subscriptions WHERE business_id = :bid AND status = 'active'"),
            {"bid": business_id},
        )
        sub_row = result.fetchone()
        if sub_row:
            current_tier_id = sub_row[0]

        repo = FeatureFlagRepository(db)
        is_enabled = await repo.is_feature_enabled_for_business(business_id, flag_id, current_tier_id)

        if not is_enabled:
            raise ForbiddenError(f"Feature '{flag_id}' is not enabled for your account or tier.")

        return business_id

    return feature_checker
