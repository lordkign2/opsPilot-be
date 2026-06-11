"""
OpsPilot — Super-Admin Module: Pydantic Validation Schemas.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.modules.auth.models import UserRole


class MaintenanceRequest(BaseModel):
    """Payload to toggle system-wide maintenance mode."""

    is_active: bool


class RoleUpdateRequest(BaseModel):
    """Payload to promote or change a user's role."""

    role: UserRole


class BroadcastRequest(BaseModel):
    """Payload to dispatch a global websocket message."""

    message: str
    event_type: str = "system_alert"


class SystemSettingsSchema(BaseModel):
    """Schema representing global system configuration settings."""

    global_mfa_requirement: bool
    strict_password_complexity: bool
    idle_session_timeout: int
    max_concurrent_sessions: int
    admin_ip_whitelist: str
    global_rate_limit: int
    allowed_cors_domains: str
    active_signing_keys_count: int
    platform_name: str
    contact_email: str
    operating_region: str
    local_currency: str
    system_timezone: str
    base_tax_rate: float
    maintenance_mode: bool
    new_registrations: bool
    debug_mode: bool
    system_log_retention_days: int
    database_quota_gb: int
    database_used_gb: int
    media_storage_quota_gb: int
    media_storage_used_gb: int

    class Config:
        from_attributes = True


class SystemSettingsUpdateSchema(BaseModel):
    """Schema representing fields that can be updated in system settings."""

    global_mfa_requirement: bool | None = None
    strict_password_complexity: bool | None = None
    idle_session_timeout: int | None = None
    max_concurrent_sessions: int | None = None
    admin_ip_whitelist: str | None = None
    global_rate_limit: int | None = None
    allowed_cors_domains: str | None = None
    active_signing_keys_count: int | None = None
    platform_name: str | None = None
    contact_email: str | None = None
    operating_region: str | None = None
    local_currency: str | None = None
    system_timezone: str | None = None
    base_tax_rate: float | None = None
    maintenance_mode: bool | None = None
    new_registrations: bool | None = None
    debug_mode: bool | None = None
    system_log_retention_days: int | None = None
    database_quota_gb: int | None = None
    database_used_gb: int | None = None
    media_storage_quota_gb: int | None = None
    media_storage_used_gb: int | None = None

