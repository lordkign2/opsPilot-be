import uuid

from pydantic import BaseModel, ConfigDict


class SubscriptionTierBase(BaseModel):
    id: str
    name: str
    description: str | None = None
    monthly_price: int = 0
    max_users: int = 5


class SubscriptionTierResponse(SubscriptionTierBase):
    model_config = ConfigDict(from_attributes=True)


class FeatureFlagBase(BaseModel):
    id: str
    description: str | None = None
    is_global_active: bool = False
    minimum_tier: str | None = None


class FeatureFlagResponse(FeatureFlagBase):
    model_config = ConfigDict(from_attributes=True)


class BusinessFeatureFlagResponse(BaseModel):
    business_id: uuid.UUID
    flag_id: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
