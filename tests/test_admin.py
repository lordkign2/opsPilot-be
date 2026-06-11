"""
OpsPilot — Super-Admin and System Observability Test Suite.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User, UserRole
from app.modules.auth.service import AuthService
from app.modules.businesses.models import Business

# ── Stateful Redis Mock for Maintenance Mode ──────────────────


class StatefulMockRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    async def get(self, key: str, *args, **kwargs) -> bytes | None:
        return self.store.get(key)

    async def set(self, key: str, value: Any, *args, **kwargs) -> bool:
        self.store[key] = value.encode() if isinstance(value, str) else value
        return True

    async def setex(self, key: str, ttl: int, value: Any, *args, **kwargs) -> bool:
        self.store[key] = value.encode() if isinstance(value, str) else value
        return True

    async def ping(self) -> bool:
        return True


@pytest.fixture
def stateful_redis() -> StatefulMockRedis:
    return StatefulMockRedis()


@pytest.fixture
async def setup_admin_data(db_session: AsyncSession) -> dict:
    """Setup a standard business, owner user, and a super-admin user."""
    # 1. Create Business
    business = Business(
        name="Admin Test Bakery",
        slug=f"admin-test-bakery-{uuid.uuid4()}",
        industry="Retail",
        is_active=True,
    )
    db_session.add(business)
    await db_session.flush()

    # 2. Create Owner User (Standard Merchant)
    owner = User(
        email=f"merchant-{uuid.uuid4()}@test.com",
        password_hash="fake_hash",
        first_name="Jane",
        last_name="Doe",
        role=UserRole.OWNER,
        business_id=business.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner)
    await db_session.flush()

    # 3. Create Super-Admin User (Global bypass identity)
    super_admin = User(
        email=f"admin-{uuid.uuid4()}@test.com",
        password_hash="fake_hash",
        first_name="Super",
        last_name="Operator",
        role=UserRole.SUPER_ADMIN,
        business_id=None,
        is_active=True,
        is_verified=True,
    )
    db_session.add(super_admin)
    await db_session.flush()

    await db_session.commit()

    # Generate JWT Tokens
    auth_service = AuthService(db_session, redis=None)
    merchant_tokens = auth_service._generate_tokens(owner)
    admin_tokens = auth_service._generate_tokens(super_admin)

    return {
        "business": business,
        "merchant": owner,
        "super_admin": super_admin,
        "merchant_token": merchant_tokens.access_token,
        "admin_token": admin_tokens.access_token,
    }


# ── Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_route_isolation(client: AsyncClient, setup_admin_data: dict):
    """Verify that standard merchants are blocked from /admin routes with 403 Forbidden."""
    merchant_token = setup_admin_data["merchant_token"]
    admin_token = setup_admin_data["admin_token"]

    # 1. Standard merchant request → Blocked with 403
    response = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {merchant_token}"})
    assert response.status_code == 403
    assert "requires super administrative privileges" in response.json()["message"]

    # 2. Anonymous request → Blocked with 401
    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 401

    # 3. Super admin request → Success 200
    response = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_system_health_telemetry(client: AsyncClient, setup_admin_data: dict):
    """Verify that GET /admin/system/health returns core connection statistics."""
    admin_token = setup_admin_data["admin_token"]

    response = await client.get("/api/v1/admin/system/health", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    res_data = response.json()["data"]
    assert "status" in res_data
    assert "services" in res_data
    assert "metrics" in res_data
    assert res_data["services"]["postgres"] == "connected"


@pytest.mark.asyncio
async def test_system_compliance_logs(client: AsyncClient, setup_admin_data: dict, db_session: AsyncSession):
    """Verify that GET /admin/system/logs returns SOC2 compliance database logs."""
    admin_token = setup_admin_data["admin_token"]

    # Pre-populate an audit log entry
    log_entry = AuditLog(
        action="user_promoted",
        module="admin",
        actor_id=setup_admin_data["super_admin"].id,
        target_id=str(setup_admin_data["merchant"].id),
        payload={"new_role": "sales_rep"},
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    db_session.add(log_entry)
    await db_session.commit()

    response = await client.get("/api/v1/admin/system/logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    res_body = response.json()
    assert res_body["success"] is True
    assert res_body["meta"]["total"] >= 1
    assert any(log["action"] == "user_promoted" for log in res_body["data"])


@pytest.mark.asyncio
async def test_maintenance_mode_enforcement(
    client: AsyncClient, setup_admin_data: dict, stateful_redis: StatefulMockRedis
):
    """Assert that active maintenance mode blocks standard users but lets super-admins pass."""
    merchant_token = setup_admin_data["merchant_token"]
    admin_token = setup_admin_data["admin_token"]

    # Override get_redis dependency with our stateful Redis mock
    app.dependency_overrides[get_redis] = lambda: stateful_redis

    # 1. Toggle maintenance mode ON
    toggle_res = await client.post(
        "/api/v1/admin/system/maintenance", json={"is_active": True}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["data"]["maintenance_mode_active"] is True

    # 2. Standard merchant requests are blocked with 503 Service Unavailable
    biz_res = await client.get("/api/v1/businesses/current", headers={"Authorization": f"Bearer {merchant_token}"})
    assert biz_res.status_code == 503
    assert "maintenance" in biz_res.json()["message"]

    # 3. Super admin requests pass through untouched
    admin_users_res = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_users_res.status_code == 200

    # 4. Toggle maintenance mode OFF
    toggle_res = await client.post(
        "/api/v1/admin/system/maintenance",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["data"]["maintenance_mode_active"] is False

    # 5. Standard merchant request works again
    biz_res = await client.get("/api/v1/businesses/current", headers={"Authorization": f"Bearer {merchant_token}"})
    assert biz_res.status_code == 200

    # Clean dependency overrides
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_business_and_user_toggles(client: AsyncClient, setup_admin_data: dict):
    """Test business activation toggle and user role promotion endpoints."""
    admin_token = setup_admin_data["admin_token"]
    business_id = setup_admin_data["business"].id
    merchant_id = setup_admin_data["merchant"].id

    # 1. Toggle Business status (Deactivate)
    toggle_res = await client.post(
        f"/api/v1/admin/businesses/{business_id}/toggle", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["data"]["is_active"] is False

    # 2. Update standard user's role (Promote)
    role_res = await client.post(
        f"/api/v1/admin/users/{merchant_id}/role",
        json={"role": "manager"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert role_res.status_code == 200
    assert role_res.json()["data"]["role"] == "manager"


@pytest.mark.asyncio
async def test_soft_delete_and_hard_purge(client: AsyncClient, setup_admin_data: dict, db_session: AsyncSession):
    """Test dual soft-delete marking and GDPR permanent purges."""
    admin_token = setup_admin_data["admin_token"]
    merchant = setup_admin_data["merchant"]
    merchant_token = setup_admin_data["merchant_token"]

    # 1. Soft delete the user
    soft_del_res = await client.delete(
        f"/api/v1/admin/users/{merchant.id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert soft_del_res.status_code == 200
    assert "deleted_at" in soft_del_res.json()["data"]

    # 2. Standard merchant is immediately rejected from authentication with 404 (NotFoundError for deleted user)
    auth_fail_res = await client.get(
        "/api/v1/businesses/current", headers={"Authorization": f"Bearer {merchant_token}"}
    )
    assert auth_fail_res.status_code == 404

    # 3. GDPR hard purge the user
    purge_res = await client.delete(
        f"/api/v1/admin/users/{merchant.id}/purge", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert purge_res.status_code == 200

    # 4. Assert user is completely deleted in the database
    stmt = select(User).where(User.id == merchant.id)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_admin_system_settings_endpoints(client: AsyncClient, setup_admin_data: dict):
    """Test retrieval and persistence of system settings configurations."""
    merchant_token = setup_admin_data["merchant_token"]
    admin_token = setup_admin_data["admin_token"]

    # 1. Standard merchant is blocked
    response = await client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {merchant_token}"})
    assert response.status_code == 403

    # 2. Super admin retrieves defaults
    response = await client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    res_data = response.json()["data"]
    assert res_data["platform_name"] == "OpsPilot Core"
    assert res_data["global_mfa_requirement"] is False

    # 3. Super admin updates settings
    update_payload = {
        "platform_name": "OpsPilot Custom Test Core",
        "global_mfa_requirement": True,
        "base_tax_rate": 8.5,
    }
    response = await client.put(
        "/api/v1/admin/settings",
        json=update_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    res_data = response.json()["data"]
    assert res_data["platform_name"] == "OpsPilot Custom Test Core"
    assert res_data["global_mfa_requirement"] is True
    assert res_data["base_tax_rate"] == 8.5

    # 4. Fetch settings again and check persistence
    response = await client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    res_data = response.json()["data"]
    assert res_data["platform_name"] == "OpsPilot Custom Test Core"
    assert res_data["global_mfa_requirement"] is True

