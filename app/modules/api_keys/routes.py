"""
OpsPilot — API Keys Module: HTTP Routes (Phase 8).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.api_keys.schemas import APIKeyCreate, APIKeyCreatedResponse
from app.modules.api_keys.service import APIKeyService
from app.modules.auth.dependencies import CurrentBusinessId, CurrentUser, require_permission
from app.shared.response import success_response

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

_manage_perm = [Depends(require_permission(Permission.API_KEYS_MANAGE))]


async def get_api_key_service(db: AsyncSession = Depends(get_db)) -> APIKeyService:
    return APIKeyService(db)


@router.post(
    "/",
    response_model=None,
    status_code=201,
    dependencies=_manage_perm,
    summary="Create a new API key",
)
async def create_api_key(
    payload: APIKeyCreate,
    current_user: CurrentUser,
    business_id: CurrentBusinessId,
    service: APIKeyService = Depends(get_api_key_service),
) -> Any:
    """
    Generate a new API key for server-to-server integrations.

    The raw key value is returned **only once** in this response.
    Store it securely — it cannot be retrieved again.
    """
    result = await service.create_key(
        payload=payload,
        business_id=business_id,
        created_by=current_user.id,
    )
    return success_response(
        data=APIKeyCreatedResponse.model_validate(result).model_dump(mode="json"),
        message="API key created. Store the raw key securely — it will not be shown again.",
    )


@router.get(
    "/",
    response_model=None,
    dependencies=_manage_perm,
    summary="List all API keys for the business",
)
async def list_api_keys(
    business_id: CurrentBusinessId,
    service: APIKeyService = Depends(get_api_key_service),
) -> Any:
    """List all API keys (metadata only — no raw key values)."""
    keys = await service.list_keys(business_id)
    return success_response(
        data=[k.model_dump(mode="json") for k in keys],
        message="API keys retrieved.",
    )


@router.delete(
    "/{key_id}",
    response_model=None,
    dependencies=_manage_perm,
    summary="Revoke an API key",
)
async def revoke_api_key(
    key_id: uuid.UUID,
    business_id: CurrentBusinessId,
    service: APIKeyService = Depends(get_api_key_service),
) -> Any:
    """Permanently revoke an API key. This action cannot be undone."""
    await service.revoke_key(key_id, business_id)
    return success_response(message="API key revoked successfully.")
