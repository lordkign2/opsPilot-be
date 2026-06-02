"""
OpsPilot — Analytics Module: Routes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache

from app.core.permissions import Permission
from app.modules.analytics.dependencies import AnalyticsServiceDep
from app.modules.auth.dependencies import CurrentBusinessId, require_permission
from app.shared.response import success_response

router = APIRouter(prefix="/analytics", tags=["Analytics"])

_analytics_read = [Depends(require_permission(Permission.ANALYTICS_READ))]


@router.get("/overview", response_model=None, dependencies=_analytics_read)
@cache(expire=300)
async def get_overview(
    business_id: CurrentBusinessId,
    analytics_service: AnalyticsServiceDep,
) -> Any:
    """Retrieve operational dashboard overview analytics."""
    data = await analytics_service.get_overview(business_id)
    return success_response(data=data, message="Dashboard overview fetched successfully.")


@router.get("/revenue", response_model=None, dependencies=_analytics_read)
@cache(expire=600)
async def get_revenue_history(
    business_id: CurrentBusinessId,
    analytics_service: AnalyticsServiceDep,
    days: int = Query(30, ge=1, le=365),
) -> Any:
    """Retrieve successful revenue trend statistics."""
    trend = await analytics_service.get_revenue_history(business_id, days=days)
    return success_response(
        data={"days": days, "trend": trend},
        message="Revenue history trends fetched successfully.",
    )


@router.get("/orders", response_model=None, dependencies=_analytics_read)
@cache(expire=300)
async def get_order_distribution(
    business_id: CurrentBusinessId,
    analytics_service: AnalyticsServiceDep,
) -> Any:
    """Retrieve order status distribution statistics."""
    data = await analytics_service.get_order_distribution(business_id)
    return success_response(data=data, message="Order status distribution fetched successfully.")
