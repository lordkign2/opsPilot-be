"""
OpsPilot — Super-Admin Operations Module: HTTP Routes.

Exposes platforms overrides and observabilities to administrators, delegating to AdminService.
"""

from __future__ import annotations

import uuid
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query

from app.db.redis import get_redis
from app.modules.admin.dependencies import AdminServiceDep
from app.modules.admin.schemas import (
    BroadcastRequest,
    MaintenanceRequest,
    RoleUpdateRequest,
    SystemSettingsSchema,
    SystemSettingsUpdateSchema,
)
from app.modules.auth.dependencies import CurrentSuperAdmin
from app.shared.response import paginated_response, success_response

router = APIRouter(prefix="/admin", tags=["Super-Admin Ops"])


# ── System Health & Telemetry ────────────────────────────────


@router.get(
    "/system/health",
    summary="Retrieve live system connection health and telemetry check",
)
async def get_system_health(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    redis: aioredis.Redis = Depends(get_redis),
) -> Any:
    """Ping PostgreSQL, Redis, WebSocket connection counts, CPU, and memory usage."""
    health_data = await service.get_system_health(redis)
    return success_response(data=health_data, message="System connection telemetry retrieved successfully.")


# ── System compliance Logs ───────────────────────────────────


@router.get(
    "/system/logs",
    summary="Read central compliance database audit logs feed",
)
async def get_system_logs(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Exposes a paginated compliance audit log feed directly inside Swagger."""
    logs, total = await service.get_system_logs(limit, offset)
    return paginated_response(
        data=logs,
        total=total,
        page=(offset // limit) + 1,
        per_page=limit,
        message="Compliance audit logs retrieved successfully.",
    )


# ── Maintenance Mode Control ─────────────────────────────────


@router.post(
    "/system/maintenance",
    summary="Toggle system-wide maintenance mode in Redis",
)
async def toggle_maintenance_mode(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    payload: MaintenanceRequest,
    redis: aioredis.Redis = Depends(get_redis),
) -> Any:
    """Toggle system-wide maintenance mode in Redis, blocking standard traffic."""
    is_active = await service.toggle_maintenance_mode(redis, payload.is_active)
    return success_response(
        data={"maintenance_mode_active": is_active},
        message=f"Maintenance mode successfully {'activated' if is_active else 'deactivated'}.",
    )


# ── Business overrides ───────────────────────────────────────


@router.get(
    "/businesses",
    summary="List all registered business workspace tenants",
)
async def list_businesses(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Returns all active/inactive businesses globally."""
    data, total = await service.list_businesses(limit, offset)
    return paginated_response(
        data=data,
        total=total,
        page=(offset // limit) + 1,
        per_page=limit,
        message="Business workspace tenants retrieved successfully.",
    )


@router.post(
    "/businesses/{business_id}/toggle",
    summary="Suspend or activate a business workspace workspace",
)
async def toggle_business_status(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    business_id: uuid.UUID,
) -> Any:
    """Deactivate or activate a business tenant, suspending access for all member users."""
    res = await service.toggle_business_status(business_id)
    return success_response(
        data=res, message=f"Business workspace successfully {'activated' if res['is_active'] else 'suspended'}."
    )


@router.delete(
    "/businesses/{business_id}",
    summary="Soft-delete a business workspace",
)
async def soft_delete_business(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    business_id: uuid.UUID,
) -> Any:
    """Soft-deletes a business workspace by stamping deleted_at timestamp."""
    res = await service.soft_delete_business(business_id)
    return success_response(data=res, message="Business workspace soft-deleted successfully.")


@router.delete(
    "/businesses/{business_id}/purge",
    summary="Cascading GDPR/cleanup hard-delete purge",
)
async def hard_purge_business(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    business_id: uuid.UUID,
) -> Any:
    """Permanently purges a business and executes a cascading relational cleanup."""
    await service.hard_purge_business(business_id)
    return success_response(
        data={"business_id": str(business_id)},
        message="Business workspace hard-deleted and purged permanently from database.",
    )


# ── User overrides ───────────────────────────────────────────


@router.get(
    "/users",
    summary="List all registered platform users globally",
)
async def list_users(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Returns all users across all business workspaces."""
    data, total = await service.list_users(limit, offset)
    return paginated_response(
        data=data,
        total=total,
        page=(offset // limit) + 1,
        per_page=limit,
        message="Platform users retrieved successfully.",
    )


@router.post(
    "/users/{user_id}/role",
    summary="Update a user's role globally",
)
async def update_user_role(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    user_id: uuid.UUID,
    payload: RoleUpdateRequest,
) -> Any:
    """Promotes or alters any user's role (including elevating to super_admin)."""
    res = await service.update_user_role(user_id, payload.role)
    return success_response(data=res, message="User role updated successfully.")


@router.post(
    "/users/{user_id}/toggle",
    summary="Deactivate or activate a user account",
)
async def toggle_user_status(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    user_id: uuid.UUID,
) -> Any:
    """Toggle a user's active status, instantly blocking access on next request if suspended."""
    res = await service.toggle_user_status(user_id)
    return success_response(
        data=res, message=f"User account successfully {'activated' if res['is_active'] else 'deactivated'}."
    )


@router.delete(
    "/users/{user_id}",
    summary="Soft-delete a user account",
)
async def soft_delete_user(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    user_id: uuid.UUID,
) -> Any:
    """Soft-deletes a user account by stamping deleted_at timestamp."""
    res = await service.soft_delete_user(user_id)
    return success_response(data=res, message="User account soft-deleted successfully.")


@router.delete(
    "/users/{user_id}/purge",
    summary="GDPR permanent hard-delete user purge",
)
async def hard_purge_user(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    user_id: uuid.UUID,
) -> Any:
    """GDPR absolute purge: deletes user permanently from database."""
    await service.hard_purge_user(user_id)
    return success_response(
        data={"user_id": str(user_id)}, message="User account hard-deleted and purged permanently from database."
    )


# ── Workflow Inspection ──────────────────────────────────────


@router.get(
    "/workflows",
    summary="Audit all workflow rules globally across all workspaces",
)
async def list_global_workflows(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Audits automated triggers and rules configured globally."""
    data, total = await service.list_global_workflows(limit, offset)
    return paginated_response(
        data=data,
        total=total,
        page=(offset // limit) + 1,
        per_page=limit,
        message="Global workflow rules audited successfully.",
    )


# ── WebSocket Direct Controls ────────────────────────────────


@router.get(
    "/websocket/sessions",
    summary="List active real-time WebSocket connection sessions",
)
async def get_websocket_sessions(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
) -> Any:
    """Retrieves metadata of all active WebSocket client sessions."""
    sessions = await service.get_websocket_sessions()
    return success_response(data=sessions, message="Active WebSocket connections retrieved successfully.")


@router.post(
    "/websocket/broadcast",
    summary="Dispatch a global system alert to all active clients",
)
async def broadcast_system_alert(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    payload: BroadcastRequest,
) -> Any:
    """Sends a system alert event to all currently active WebSocket connections globally."""
    count = await service.broadcast_system_alert(payload.message, payload.event_type)
    return success_response(
        data={"broadcast_count": count}, message=f"Global system alert fanned out to {count} active sessions."
    )


# ── Global System Settings ───────────────────────────────────


@router.get(
    "/settings",
    summary="Retrieve global system configuration settings",
    response_model=Any,
)
async def get_system_settings(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
) -> Any:
    """Fetches all platform system configuration parameters from the database."""
    settings_data = await service.get_settings()
    return success_response(data=settings_data, message="System settings retrieved successfully.")


@router.put(
    "/settings",
    summary="Update global system configuration settings",
    response_model=Any,
)
async def update_system_settings(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
    payload: SystemSettingsUpdateSchema,
) -> Any:
    """Updates configuration parameter fields on the system settings record in the database."""
    updated_data = await service.update_settings(payload.model_dump(exclude_unset=True))
    return success_response(data=updated_data, message="System settings updated successfully.")


@router.get(
    "/telemetry",
    summary="Retrieve platform overview telemetry metrics",
    response_model=Any,
)
async def get_platform_telemetry(
    admin: CurrentSuperAdmin,
    service: AdminServiceDep,
) -> Any:
    """Fetches total NRR, churn rate, user location coordinates, average latency, and error rate."""
    data = await service.get_telemetry()
    return success_response(data=data, message="Telemetry metrics retrieved successfully.")


