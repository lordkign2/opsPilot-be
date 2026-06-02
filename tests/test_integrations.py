"""
OpsPilot — Integration Ecosystem: Automated Test Suite.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.integrations.communications.email import send_transactional_email
from app.integrations.communications.push import send_push_notification
from app.integrations.communications.sms import send_sms
from app.modules.businesses.models import Business
from app.modules.customers.models import Customer
from app.modules.orders.models import Order


@pytest.fixture
async def integration_test_data(db_session: AsyncSession) -> dict[str, Any]:
    """Sets up an active business for integration test scopes."""
    business = Business(
        name="Fintech SME Hub",
        slug=f"fintech-sme-hub-{uuid.uuid4()}",
        industry="Services",
    )
    db_session.add(business)
    await db_session.flush()
    await db_session.commit()
    return {"business": business}


@pytest.mark.asyncio
async def test_whatsapp_webhook_verification(client: AsyncClient):
    """Verify Meta challenge verification handshake routing and security parameters."""
    # 1. Invalid verification token -> 403 Forbidden
    response_fail = await client.get(
        "/api/v1/integrations/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "11223344",
            "hub.verify_token": "wrong_token",
        },
    )
    assert response_fail.status_code == 403

    # 2. Valid token -> 200 OK with challenge body
    # Standard fallback verify token matches "opspilot_default_verify_token"
    response_success = await client.get(
        "/api/v1/integrations/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "11223344",
            "hub.verify_token": "opspilot_default_verify_token",
        },
    )
    assert response_success.status_code == 200
    assert response_success.text == "11223344"


@pytest.mark.asyncio
async def test_whatsapp_conversational_ordering_and_ai(
    client: AsyncClient, integration_test_data: dict[str, Any], db_session: AsyncSession
):
    """Test incoming customer chats, dynamic Customer onboarding, and automatic Order checkout."""
    sender_phone = "2348033445566"

    # Simulate customer requesting to buy/order a product
    incoming_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "12345",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "123", "phone_number_id": "1"},
                            "messages": [
                                {
                                    "from": sender_phone,
                                    "id": "msg_001",
                                    "timestamp": "12345678",
                                    "type": "text",
                                    "text": {"body": "I want to place an order for custom chocolate cakes"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    # Webhook triggers background tasks
    response = await client.post("/api/v1/integrations/whatsapp", json=incoming_payload)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Yield to let the asynchronous out-of-band task finalize its db commits
    await asyncio.sleep(1.5)

    # 1. Assert that the customer was automatically created/onboarded scoping the phone number
    stmt_customer = select(Customer).where(Customer.phone == sender_phone)
    res_customer = await db_session.execute(stmt_customer)
    customer = res_customer.scalars().first()
    assert customer is not None
    assert customer.phone == sender_phone

    # 2. Assert that the Order was automatically generated scoping the customer ID
    stmt_order = select(Order).where(Order.customer_id == customer.id)
    res_order = await db_session.execute(stmt_order)
    order = res_order.scalars().first()
    assert order is not None
    assert float(order.total_amount) == 15000.00
    assert "pending" in order.status.value


@pytest.mark.asyncio
async def test_paystack_signature_verification_and_event_broadcast(
    client: AsyncClient, integration_test_data: dict[str, Any]
):
    """Test cryptographic Paystack signature checks and subsequent event_bus broadcasts."""
    business_id = str(integration_test_data["business"].id)
    order_id = str(uuid.uuid4())
    ref = f"ref-{uuid.uuid4()}"

    webhook_payload = {
        "event": "charge.success",
        "data": {
            "reference": ref,
            "amount": 1500000,  # ₦15,000.00 in Kobo
            "status": "success",
            "customer": {"email": "checkout@client.com"},
            "metadata": {
                "business_id": business_id,
                "order_id": order_id,
            },
        },
    }

    # 1. Missing signature header -> 401
    resp_no_sig = await client.post("/api/v1/integrations/payments/paystack/webhook", json=webhook_payload)
    assert resp_no_sig.status_code == 401

    # 2. Invalid signature header -> 401
    resp_bad_sig = await client.post(
        "/api/v1/integrations/payments/paystack/webhook",
        json=webhook_payload,
        headers={"x-paystack-signature": "invalid_signature_hash"},
    )
    assert resp_bad_sig.status_code == 401

    # 3. Valid signature -> 200 OK & triggers event_bus dispatch
    import json

    raw_payload_bytes = json.dumps(webhook_payload, separators=(",", ":")).encode("utf-8")

    # Standard fallback webhook secret matches "paystack_sandbox_secret"
    valid_sig = hmac.new(b"paystack_sandbox_secret", raw_payload_bytes, hashlib.sha512).hexdigest()

    event_emitted = False
    emitted_payload = {}

    @event_bus.on("payment.success")
    async def capture_success(event: Any):
        nonlocal event_emitted, emitted_payload
        event_emitted = True
        emitted_payload = event.payload

    resp_valid = await client.post(
        "/api/v1/integrations/payments/paystack/webhook",
        content=raw_payload_bytes,
        headers={"x-paystack-signature": valid_sig, "Content-Type": "application/json"},
    )
    assert resp_valid.status_code == 200

    # Assert event was fanned out successfully via local EventBus hook
    assert event_emitted is True
    assert emitted_payload["business_id"] == business_id
    assert emitted_payload["order_id"] == order_id
    assert emitted_payload["amount"] == 15000.0


@pytest.mark.asyncio
async def test_flutterwave_hash_verification(client: AsyncClient, integration_test_data: dict[str, Any]):
    """Test cryptographic Flutterwave secret hash verification checks."""
    business_id = str(integration_test_data["business"].id)
    order_id = str(uuid.uuid4())
    ref = f"flw-ref-{uuid.uuid4()}"

    webhook_payload = {
        "status": "successful",
        "tx_ref": ref,
        "amount": 25000.0,
        "customer": {"email": "customer@flw.com"},
        "meta": {
            "business_id": business_id,
            "order_id": order_id,
        },
    }

    # 1. Missing header -> 401
    resp_no_hash = await client.post("/api/v1/integrations/payments/flutterwave/webhook", json=webhook_payload)
    assert resp_no_hash.status_code == 401

    # 2. Bad verification hash -> 401
    resp_bad_hash = await client.post(
        "/api/v1/integrations/payments/flutterwave/webhook",
        json=webhook_payload,
        headers={"verif-hash": "wrong_flutterwave_hash"},
    )
    assert resp_bad_hash.status_code == 401

    # 3. Valid verification hash -> 200 OK & triggers event_bus dispatch
    # Default verify hash: "flutterwave_sandbox_hash"
    resp_valid = await client.post(
        "/api/v1/integrations/payments/flutterwave/webhook",
        json=webhook_payload,
        headers={"verif-hash": "flutterwave_sandbox_hash"},
    )
    assert resp_valid.status_code == 200


@pytest.mark.asyncio
async def test_communications_dispatchers():
    """Verify sandboxed communications execution routes for email, SMS, and push notifications."""
    assert await send_sms("+234800000000", "Hello Test SMS!") is True
    assert await send_transactional_email("test@email.com", "Test Email", "<p>Content</p>") is True

    # Invalid push token fails
    assert await send_push_notification("invalid_token", "Push Title", "Push Body") is False
    # Valid push token resolves True in mock sandbox
    assert await send_push_notification("ExponentPushToken[12345]", "Push Title", "Push Body") is True
