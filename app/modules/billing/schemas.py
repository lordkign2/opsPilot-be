import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    tier_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime | None = None
    cancel_at_period_end: bool

    model_config = ConfigDict(from_attributes=True)


class CheckoutSessionResponse(BaseModel):
    authorization_url: str
    reference: str


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID | None = None
    amount_paid: int
    currency: str
    status: str
    paid_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
