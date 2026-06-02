import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_business_id
from app.modules.billing.schemas import CheckoutSessionResponse, SubscriptionResponse
from app.modules.billing.service import BillingService

logger = get_logger("opspilot.billing.routes")
router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    business_id: uuid.UUID = Depends(get_current_business_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    service = BillingService(db)
    sub = await service.get_or_create_subscription(business_id)
    return sub


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    tier_id: str,
    business_id: uuid.UUID = Depends(get_current_business_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    service = BillingService(db)
    checkout = await service.generate_checkout_session(business_id, tier_id)
    return checkout


@router.post("/webhook")
async def paystack_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Endpoint for Paystack webhooks.
    In production, you MUST verify the Paystack signature using HMAC SHA512.
    """
    # Note: signature validation goes here
    payload = await request.json()
    service = BillingService(db)
    await service.handle_webhook_event(payload)
    return {"status": "success"}
