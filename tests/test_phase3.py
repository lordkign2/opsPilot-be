"""
OpsPilot — Phase 3 Test Suite.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.notifications.events  # noqa: F401
from app.core.events import event_bus
from app.db.session import async_session_factory
from app.modules.ai.models import AILog
from app.modules.auth.models import User, UserRole
from app.modules.auth.service import AuthService
from app.modules.businesses.models import Business
from app.modules.customers.models import Customer
from app.modules.notifications.models import Notification
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentStatus


@pytest.fixture
async def setup_test_data(db_session: AsyncSession) -> dict:
    """Setup a sample business, user, customer, order, and payment for testing."""
    # 1. Create Business
    business = Business(
        name="Test SME Bakery",
        slug=f"test-sme-bakery-{uuid.uuid4()}",
        industry="Retail",
    )
    db_session.add(business)
    await db_session.flush()

    # 2. Create Owner User
    owner = User(
        email=f"owner-{uuid.uuid4()}@testbakery.com",
        password_hash="fake_hash",
        first_name="John",
        last_name="Doe",
        role=UserRole.OWNER,
        business_id=business.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner)
    await db_session.flush()

    # 3. Create Customer
    customer = Customer(
        name="Alice Smith",
        phone="+2348012345678",
        email="alice@gmail.com",
        notes="Loves croissants.",
        business_id=business.id,
    )
    db_session.add(customer)
    await db_session.flush()

    # 4. Create Completed Order
    order1 = Order(
        status=OrderStatus.COMPLETED,
        total_amount=15000.0,
        notes="Completed order",
        customer_id=customer.id,
        business_id=business.id,
    )
    db_session.add(order1)
    await db_session.flush()

    # 5. Create Successful Payment for Order 1
    payment1 = Payment(
        order_id=order1.id,
        provider="paystack",
        tx_ref=f"tx-{uuid.uuid4()}",
        status=PaymentStatus.SUCCESS,
        amount=15000.0,
    )
    db_session.add(payment1)
    await db_session.flush()

    # 6. Create Pending Order
    order2 = Order(
        status=OrderStatus.PENDING,
        total_amount=5000.0,
        notes="Pending order",
        customer_id=customer.id,
        business_id=business.id,
    )
    db_session.add(order2)
    await db_session.flush()

    await db_session.commit()

    # Generate JWT Token using AuthService
    auth_service = AuthService(db_session, redis=None)
    token_data = auth_service._generate_tokens(owner)

    return {
        "business": business,
        "owner": owner,
        "customer": customer,
        "order1": order1,
        "payment1": payment1,
        "order2": order2,
        "token": token_data.access_token,
    }


@pytest.mark.asyncio
async def test_notifications_lifecycle(client: AsyncClient, setup_test_data: dict, db_session: AsyncSession):
    """Test Notifications list, read status modification and read all alerts endpoints."""
    token = setup_test_data["token"]
    business = setup_test_data["business"]
    owner = setup_test_data["owner"]
    headers = {"Authorization": f"Bearer {token}"}

    # Pre-populate 2 notifications
    n1 = Notification(
        title="Alert 1",
        message="Message 1",
        business_id=business.id,
        user_id=owner.id,
        read=False,
    )
    n2 = Notification(
        title="Alert 2",
        message="Message 2",
        business_id=business.id,
        user_id=owner.id,
        read=False,
    )
    db_session.add_all([n1, n2])
    await db_session.commit()

    # 1. List notifications
    response = await client.get("/api/v1/notifications/", headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["meta"]["total"] >= 2

    # 2. Mark specific notification read
    patch_response = await client.patch(f"/api/v1/notifications/{n1.id}/read", headers=headers)
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["read"] is True

    # 3. Mark all read
    post_response = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert post_response.status_code == 200
    assert post_response.json()["success"] is True


@pytest.mark.asyncio
async def test_analytics_endpoints(client: AsyncClient, setup_test_data: dict):
    """Test Overview, Revenue trends, and Order distribution analytics endpoints."""
    token = setup_test_data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Overview stats
    response = await client.get("/api/v1/analytics/overview", headers=headers)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["data"]["total_revenue"] == 15000.0
    assert res_json["data"]["total_customers"] == 1
    assert res_json["data"]["total_orders"] == 2

    # 2. Revenue trends
    response = await client.get("/api/v1/analytics/revenue?days=7", headers=headers)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert len(res_json["data"]["trend"]) == 7

    # 3. Order distribution
    response = await client.get("/api/v1/analytics/orders", headers=headers)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["data"]["total_orders"] == 2
    assert "completed" in res_json["data"]["distribution"]


@pytest.mark.asyncio
async def test_ai_mock_fallback_endpoints(client: AsyncClient, setup_test_data: dict, db_session: AsyncSession):
    """Test AI assistant endpoints using the rich mock fallback system (no API key configured)."""
    token = setup_test_data["token"]
    customer = setup_test_data["customer"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Chat Endpoint
    chat_payload = {"message": "Give me a summary of my store performance."}
    response = await client.post("/api/v1/ai/chat", json=chat_payload, headers=headers)
    assert response.status_code == 200
    assert response.headers.get("x-vercel-ai-data-stream") == "v1"
    assert "mock fallback response" in response.text

    # 2. Summary Endpoint
    summary_payload = {"timeframe": "weekly"}
    response = await client.post("/api/v1/ai/summary", json=summary_payload, headers=headers)
    assert response.status_code == 200
    assert "summary" in response.json()["data"]

    # 3. Recommendations Endpoint
    response = await client.post("/api/v1/ai/recommendations", headers=headers)
    assert response.status_code == 200
    assert "recommendations" in response.json()["data"]
    assert len(response.json()["data"]["recommendations"]) >= 2

    # 4. Customer Insights Endpoint
    insights_payload = {"customer_id": str(customer.id)}
    response = await client.post("/api/v1/ai/customer-insights", json=insights_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["customer_id"] == str(customer.id)
    assert "insights" in response.json()["data"]

    # Verify AI logs were written to database
    stmt = select(AILog)
    res = await db_session.execute(stmt)
    logs = res.scalars().all()
    assert len(logs) >= 4


@pytest.mark.asyncio
async def test_event_driven_notifications(setup_test_data: dict):
    """Test that event listeners generate appropriate Notifications in response to events."""
    business_id = setup_test_data["business"].id
    order_id = uuid.uuid4()
    customer_id = setup_test_data["customer"].id

    await event_bus.emit(
        "order.created",
        {
            "order_id": str(order_id),
            "business_id": str(business_id),
            "customer_id": str(customer_id),
            "amount": 25000.0,
        },
        source_module="orders",
    )

    # Verify order created notification exists in db
    async with async_session_factory() as db:
        stmt = select(Notification).where(Notification.business_id == business_id)
        result = await db.execute(stmt)
        notifications = result.scalars().all()
        assert len(notifications) == 1
        assert "25,000.00" in notifications[0].message
        assert notifications[0].title == "New Order Created"

        # Clean up the test notification so it doesn't pollute subsequent tests
        await db.delete(notifications[0])
        await db.commit()
