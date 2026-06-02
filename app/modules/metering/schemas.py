import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UsageMeterResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    metric_name: str
    cycle_start_date: datetime
    cycle_end_date: datetime
    current_usage: int

    model_config = ConfigDict(from_attributes=True)
