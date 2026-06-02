import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.billing.models import Subscription
from app.modules.billing.paystack_client import PaystackClient
from app.modules.billing.repository import BillingRepository
from app.modules.businesses.repository import BusinessRepository


class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BillingRepository(db)
        self.business_repo = BusinessRepository(db)
        self.paystack = PaystackClient()

    async def get_or_create_subscription(self, business_id: uuid.UUID) -> Subscription:
        sub = await self.repo.get_subscription(business_id)
        if not sub:
            sub = Subscription(business_id=business_id, tier_id="free", status="active")
            sub = await self.repo.upsert_subscription(sub)
            await self.db.commit()
        return sub

    async def generate_checkout_session(self, business_id: uuid.UUID, tier_id: str) -> dict[str, Any]:
        """
        Generate a checkout link for a business to subscribe.
        For phase 10 we map 'pro' to a generic amount.
        """
        business = await self.business_repo.get_by_id(business_id)
        if not business:
            raise ValueError("Business not found")

        amount = 1000000 if tier_id == "pro" else 5000000  # 10,000 NGN or 50,000 NGN (in kobo)
        # Email can be dummy if business model doesn't have it, or fetch from owner

        # We need the user email, so we fetch the owner.
        owner = await self.db.get(User, business.owner_id)
        email = owner.email if owner else "billing@opspilot.app"

        paystack_res = await self.paystack.initialize_transaction(email=email, amount=amount)
        if not paystack_res.get("status"):
            raise HTTPException(status_code=400, detail="Failed to initialize checkout with Paystack")

        data = paystack_res.get("data", {})
        return {"authorization_url": data.get("authorization_url"), "reference": data.get("reference")}

    async def handle_webhook_event(self, event: dict[str, Any]) -> None:
        """
        Handle incoming paystack webhooks.
        """
        event_type = event.get("event")
        data = event.get("data", {})

        if event_type == "charge.success":
            _reference = data.get("reference")
            _amount = data.get("amount", 0)

            # Simulated matching for Phase 10 demo: we don't have metadata with business_id often unless passed in initialize
            # We would normally extract business_id from metadata
            # For now, we will just log it.
            pass
        elif event_type == "subscription.create" or event_type == "subscription.disable":
            pass

        await self.db.commit()
