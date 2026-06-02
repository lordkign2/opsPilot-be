"""
OpsPilot — Payments Module: Routes.
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.core.permissions import Permission
from app.modules.auth.dependencies import CurrentBusinessId, require_permission
from app.modules.payments.dependencies import PaymentServiceDep
from app.modules.payments.schemas import (
    PaymentInitialize,
    PaymentResponse,
    PaymentWebhook,
)
from app.shared.response import success_response

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/",
    response_model=None,
    status_code=201,
    dependencies=[Depends(require_permission(Permission.PAYMENTS_INITIALIZE))],
)
async def initialize_payment(
    payload: PaymentInitialize,
    business_id: CurrentBusinessId,
    payment_service: PaymentServiceDep,
) -> Any:
    """Initialize a new payment for an order."""
    payment = await payment_service.initialize_payment(business_id, payload)
    return success_response(
        data=PaymentResponse.model_validate(payment).model_dump(mode="json"),
        message="Payment initialized.",
    )


@router.get(
    "/verify/{tx_ref}", response_model=None, dependencies=[Depends(require_permission(Permission.PAYMENTS_VERIFY))]
)
async def verify_payment(
    tx_ref: str,
    payment_service: PaymentServiceDep,
) -> Any:
    """Verify payment status via reference."""
    payment = await payment_service.verify_payment(tx_ref)
    return success_response(
        data=PaymentResponse.model_validate(payment).model_dump(mode="json"),
        message="Payment verification complete.",
    )


@router.post("/webhook", response_model=None)
async def payment_webhook(
    payload: PaymentWebhook,
    payment_service: PaymentServiceDep,
) -> Any:
    """Handle provider webhooks (unauthenticated public endpoint)."""
    # Note: In production, verify provider webhook signature here.
    await payment_service.handle_webhook(payload.event, payload.data)
    return success_response(message="Webhook processed.")
