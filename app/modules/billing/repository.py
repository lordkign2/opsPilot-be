import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import Invoice, Subscription


class BillingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_subscription(self, business_id: uuid.UUID) -> Subscription | None:
        result = await self.db.execute(select(Subscription).where(Subscription.business_id == business_id))
        return result.scalar_one_or_none()

    async def get_subscription_by_paystack_code(self, code: str) -> Subscription | None:
        result = await self.db.execute(select(Subscription).where(Subscription.paystack_subscription_code == code))
        return result.scalar_one_or_none()

    async def upsert_subscription(self, subscription: Subscription) -> Subscription:
        # Simple merge works if ID is known, but upsert via business_id is safer if ID is not known
        merged = await self.db.merge(subscription)
        await self.db.flush()
        return merged

    async def create_invoice(self, invoice: Invoice) -> Invoice:
        self.db.add(invoice)
        await self.db.flush()
        return invoice

    async def get_invoice_by_reference(self, reference: str) -> Invoice | None:
        result = await self.db.execute(select(Invoice).where(Invoice.paystack_reference == reference))
        return result.scalar_one_or_none()
