import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feature_flags.models import BusinessFeatureFlag, FeatureFlag


class FeatureFlagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_flag(self, flag_id: str) -> FeatureFlag | None:
        result = await self.db.execute(select(FeatureFlag).where(FeatureFlag.id == flag_id))
        return result.scalar_one_or_none()

    async def get_business_override(self, business_id: uuid.UUID, flag_id: str) -> BusinessFeatureFlag | None:
        result = await self.db.execute(
            select(BusinessFeatureFlag).where(
                BusinessFeatureFlag.business_id == business_id,
                BusinessFeatureFlag.flag_id == flag_id,
            )
        )
        return result.scalar_one_or_none()

    async def is_feature_enabled_for_business(
        self, business_id: uuid.UUID, flag_id: str, current_tier_id: str = "free"
    ) -> bool:
        """
        Determines if a feature is enabled for a business.
        Logic:
        1. Check for a direct business override.
        2. If no override, check if the global flag is active or if the business tier meets the minimum.
        """
        override = await self.get_business_override(business_id, flag_id)
        if override:
            return override.is_active

        flag = await self.get_flag(flag_id)
        if not flag:
            return False  # Feature doesn't exist

        if flag.is_global_active:
            return True

        # Simplified tier check: normally you'd assign a numerical weight to tiers to check >=
        # For this phase, if a minimum tier is required, and they match it, allow it.
        # Ideally, we would have a 'tier hierarchy' check.
        # We will assume 'enterprise' > 'pro' > 'free' by weight in a robust implementation.
        if flag.minimum_tier:
            # Hardcoded hierarchy for demonstration
            hierarchy = {"free": 0, "pro": 1, "enterprise": 2}
            req_level = hierarchy.get(flag.minimum_tier, 0)
            user_level = hierarchy.get(current_tier_id, 0)
            return user_level >= req_level

        return False
