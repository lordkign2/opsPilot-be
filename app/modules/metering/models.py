"""
OpsPilot — Usage Metering: Models.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageMeter(Base):
    """
    Tracks consumption for a given business over a specific billing cycle.
    """

    __tablename__ = "usage_meters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)

    # e.g., 'ai_tokens', 'workflow_executions', 'whatsapp_messages'
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)

    cycle_start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cycle_end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    current_usage: Mapped[int] = mapped_column(Integer, default=0)

    # Ensure a single meter record per metric per cycle for a business
    __table_args__ = (
        UniqueConstraint("business_id", "metric_name", "cycle_start_date", name="uq_business_metric_cycle"),
    )
