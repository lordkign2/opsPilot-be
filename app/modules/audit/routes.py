"""
OpsPilot — Audit Module: HTTP Routes (Phase 8).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.audit.schemas import AuditLogResponse
from app.modules.audit.service import AuditService
from app.modules.auth.dependencies import (
    CurrentBusinessId,
    CurrentSuperAdmin,
    require_permission,
)
from app.shared.response import paginated_response

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


async def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(db)


@router.get(
    "/",
    response_model=None,
    summary="[Super-Admin] Global audit log feed",
)
async def get_global_audit_logs(
    _admin: CurrentSuperAdmin,
    service: AuditService = Depends(get_audit_service),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Any:
    """Paginated global audit log feed — accessible to super-admins only."""
    logs, total = await service.get_logs(limit=limit, offset=offset)
    data = [AuditLogResponse.model_validate(log).model_dump(mode="json") for log in logs]
    return paginated_response(
        data=data,
        total=total,
        page=(offset // limit) + 1,
        per_page=limit,
        message="Global audit logs retrieved.",
    )


@router.get(
    "/business",
    response_model=None,
    dependencies=[Depends(require_permission(Permission.AUDIT_READ))],
    summary="Business-scoped audit log",
)
async def get_business_audit_logs(
    business_id: CurrentBusinessId,
    service: AuditService = Depends(get_audit_service),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Any:
    """
    Paginated audit log scoped to the authenticated user's business.
    Accessible to OWNER and MANAGER roles (audit.read permission).
    """
    logs, total = await service.get_logs_by_business(business_id=business_id, limit=limit, offset=offset)
    data = [AuditLogResponse.model_validate(log).model_dump(mode="json") for log in logs]
    return paginated_response(
        data=data,
        total=total,
        page=(offset // limit) + 1,
        per_page=limit,
        message="Business audit logs retrieved.",
    )
