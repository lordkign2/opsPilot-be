import uuid

import pytest
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.modules.auth.models import User
from app.modules.businesses.models import Business
from app.modules.feature_flags.dependencies import require_feature
from app.modules.feature_flags.models import BusinessFeatureFlag, FeatureFlag


@pytest.fixture
def mock_feature_app():
    app = FastAPI()

    # Create a protected endpoint
    @app.get("/protected")
    async def protected_route(business_id: uuid.UUID = Depends(require_feature("advanced_ai"))):
        return {"status": "success", "business_id": str(business_id)}

    return app


@pytest.mark.asyncio
async def test_require_feature_global_active(db_session: AsyncSession):
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

    # Setup global feature
    flag_id = f"advanced_ai_{uuid.uuid4()}"
    flag = FeatureFlag(id=flag_id, is_global_active=True)
    db_session.add(flag)
    await db_session.commit()

    checker = require_feature(flag_id)

    # Check it passes
    result = await checker(business_id, db_session)
    assert result == business_id


@pytest.mark.asyncio
async def test_require_feature_not_active(db_session: AsyncSession):
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

    # Setup global feature that is OFF
    flag_id = f"advanced_ai_{uuid.uuid4()}"
    flag = FeatureFlag(id=flag_id, is_global_active=False)
    db_session.add(flag)
    await db_session.commit()

    checker = require_feature(flag_id)

    with pytest.raises(ForbiddenError):
        await checker(business_id, db_session)


@pytest.mark.asyncio
async def test_require_feature_business_override(db_session: AsyncSession):
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

    # Setup global feature that is OFF
    flag_id = f"advanced_ai_{uuid.uuid4()}"
    flag = FeatureFlag(id=flag_id, is_global_active=False)
    db_session.add(flag)
    await db_session.flush()

    # Add override
    override = BusinessFeatureFlag(business_id=business_id, flag_id=flag_id, is_active=True)
    db_session.add(override)
    await db_session.commit()

    checker = require_feature(flag_id)

    # Should pass because of override
    result = await checker(business_id, db_session)
    assert result == business_id
