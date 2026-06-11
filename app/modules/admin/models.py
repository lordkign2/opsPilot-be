"""
OpsPilot — System Settings Configuration: Models.
"""

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    # MFA & Auth Policy
    global_mfa_requirement: Mapped[bool] = mapped_column(Boolean, default=False)
    strict_password_complexity: Mapped[bool] = mapped_column(Boolean, default=False)
    idle_session_timeout: Mapped[int] = mapped_column(Integer, default=15)
    max_concurrent_sessions: Mapped[int] = mapped_column(Integer, default=1)
    admin_ip_whitelist: Mapped[str] = mapped_column(Text, default="[]")  # JSON CIDR array
    global_rate_limit: Mapped[int] = mapped_column(Integer, default=2500)
    allowed_cors_domains: Mapped[str] = mapped_column(String(255), default="*.opspilot.io, api.partner-hub.com")
    active_signing_keys_count: Mapped[int] = mapped_column(Integer, default=3)

    # General Information & Platform
    platform_name: Mapped[str] = mapped_column(String(100), default="OpsPilot Core")
    contact_email: Mapped[str] = mapped_column(String(100), default="sysadmin@opspilot.ng")
    operating_region: Mapped[str] = mapped_column(String(100), default="Nigeria (Primary)")

    # Localization
    local_currency: Mapped[str] = mapped_column(String(50), default="NGN (₦)")
    system_timezone: Mapped[str] = mapped_column(String(50), default="WAT (UTC+1)")
    base_tax_rate: Mapped[float] = mapped_column(Float, default=7.5)

    # Infrastructure Controls
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    new_registrations: Mapped[bool] = mapped_column(Boolean, default=True)
    debug_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    # Storage & Retention
    system_log_retention_days: Mapped[int] = mapped_column(Integer, default=60)
    database_quota_gb: Mapped[int] = mapped_column(Integer, default=100)
    database_used_gb: Mapped[int] = mapped_column(Integer, default=45)
    media_storage_quota_gb: Mapped[int] = mapped_column(Integer, default=500)
    media_storage_used_gb: Mapped[int] = mapped_column(Integer, default=410)
