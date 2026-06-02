"""
OpsPilot — Feature Flags & Tier Management: Models.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SubscriptionTier(Base):
    __tablename__ = "subscription_tiers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # type: ignore[assignment]
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    monthly_price: Mapped[int] = mapped_column(default=0)  # in lowest denomination (kobo/cents)
    max_users: Mapped[int] = mapped_column(default=5)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # type: ignore[assignment]
    description: Mapped[str | None] = mapped_column(String(255))
    is_global_active: Mapped[bool] = mapped_column(Boolean, default=False)
    minimum_tier: Mapped[str | None] = mapped_column(ForeignKey("subscription_tiers.id"), nullable=True)


class BusinessFeatureFlag(Base):
    __tablename__ = "business_feature_flags"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    flag_id: Mapped[str] = mapped_column(ForeignKey("feature_flags.id", ondelete="CASCADE"), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Override the global/tier setting
