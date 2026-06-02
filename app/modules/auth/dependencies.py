"""
OpsPilot — Auth Module: FastAPI Dependencies.

Provides `get_current_user` and role-checking dependencies
for injection into protected routes.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.permissions import Permission, get_role_permissions
from app.db.redis import get_redis
from app.db.session import get_db
from app.modules.auth.models import User, UserRole
from app.modules.auth.service import AuthService

# ── Bearer Token Extraction ──────────────────────────────────
security_scheme = HTTPBearer(auto_error=False)


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> AuthService:
    """Build an AuthService instance with request-scoped dependencies."""
    return AuthService(db=db, redis=redis)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """
    FastAPI dependency that extracts and validates the JWT from
    the Authorization header, returning the authenticated User.
    """
    if not credentials:
        raise UnauthorizedError("Missing authentication token.")

    return await auth_service.get_current_user(credentials.credentials)


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Ensures the user is active."""
    if not user.is_active:
        raise ForbiddenError("Your account has been deactivated.")
    return user


# ── Role-Based Access ────────────────────────────────────────


def require_role(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    """
    Dependency factory that restricts access to users with
    specific roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.OWNER))])
    """

    async def role_checker(
        user: User = Depends(get_current_active_user),
    ) -> User:
        if user.role not in roles:
            raise ForbiddenError(f"This action requires one of: {', '.join(r.value for r in roles)}")
        return user

    return role_checker


# ── Type Aliases ─────────────────────────────────────────────
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_super_admin(
    user: User = Depends(get_current_active_user),
) -> User:
    """Ensures the user has the SUPER_ADMIN role."""
    if user.role != UserRole.SUPER_ADMIN:
        raise ForbiddenError("This endpoint requires super administrative privileges.")
    return user


CurrentSuperAdmin = Annotated[User, Depends(get_current_super_admin)]


async def get_current_business_id(
    user: User = Depends(get_current_active_user),
) -> uuid.UUID:
    """Ensures the user belongs to a business and returns the business ID."""
    if not user.business_id:
        raise ForbiddenError("You must be assigned to a business to perform this action.")
    return user.business_id


CurrentBusinessId = Annotated[uuid.UUID, Depends(get_current_business_id)]


# ── Permission-Based Access ──────────────────────────────


def require_permission(*permissions: Permission) -> Callable[..., Awaitable[User]]:
    """
    Dependency factory that enforces fine-grained action-scoped permissions.

    Checks the caller's role against the static role→permissions matrix.
    No extra DB roundtrip — permissions are resolved from the role in-memory.

    Usage::

        @router.get("/analytics", dependencies=[Depends(require_permission(Permission.ANALYTICS_READ))])
        async def get_analytics(...): ...
    """

    async def permission_checker(
        user: User = Depends(get_current_active_user),
    ) -> User:
        granted = get_role_permissions(user.role.value)
        for perm in permissions:
            if perm not in granted:
                raise ForbiddenError(f"Permission denied: '{perm.value}' is required for this action.")
        return user

    return permission_checker


# ── Dual-Auth Principal (JWT + API Key) ────────────────────────


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> User:
    """
    Resolve the current authenticated principal from either:
    1. ``Authorization: Bearer <jwt>`` header (standard user session)
    2. ``X-API-Key: opk_...`` header (server-to-server API key)

    Raises UnauthorizedError if neither credential is provided or valid.
    """
    # Try JWT Bearer first
    if credentials:
        auth_service = AuthService(db=db, redis=redis)
        return await auth_service.get_current_user(credentials.credentials)

    # Fall back to API key authentication
    if x_api_key:
        from app.modules.api_keys.dependencies import authenticate_api_key

        return await authenticate_api_key(api_key=x_api_key, db=db)

    raise UnauthorizedError("Authentication required: provide a Bearer token or X-API-Key.")


CurrentPrincipal = Annotated[User, Depends(get_current_principal)]
