import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.modules.auth.models import User
from app.modules.businesses.models import Business
from app.modules.metering.service import MeteringService


@pytest.mark.asyncio
async def test_metering_increment_and_limits(db_session: AsyncSession):
    # Setup business
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"test{user_id}@example.com",
        password_hash="pw",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    business_id = uuid.uuid4()
    business = Business(id=business_id, name="Test Business", slug=f"test-{business_id}", owner_id=user_id)
    db_session.add(business)
    await db_session.flush()
    # Assume tier is 'free' because of our mock fallback in the service

    service = MeteringService(db_session)

    # 1. Increment usage by 5000 tokens
    await service.increment_usage(business_id, "ai_tokens", 5000)

    # Check limit should pass (free limit is 10,000)
    try:
        await service.check_usage_limit(business_id, "ai_tokens", 100)
    except ForbiddenError:
        pytest.fail("Should not raise limit error for 5100 total usage")

    # 2. Increment usage by 6000 tokens (total 11000)
    await service.increment_usage(business_id, "ai_tokens", 6000)

    # 3. Check limit should now fail
    with pytest.raises(ForbiddenError):
        await service.check_usage_limit(business_id, "ai_tokens", 100)
