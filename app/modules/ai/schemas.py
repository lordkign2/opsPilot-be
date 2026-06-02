"""
OpsPilot — AI Module: Schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    message: str = Field(..., description="Message payload to send to the AI business assistant.")


class AIChatResponse(BaseModel):
    reply: str = Field(..., description="AI assistant generated textual response.")


class AISummaryRequest(BaseModel):
    timeframe: str = Field("daily", description="Format timeframe, e.g. daily, weekly, monthly.")


class AISummaryResponse(BaseModel):
    summary: str = Field(..., description="AI generated markdown performance and sales summary.")


class AIRecommendation(BaseModel):
    title: str
    description: str
    action_type: str
    impact_score: int = Field(..., ge=1, le=5)
    metadata: dict[str, Any] | None = None


class AIRecommendationsResponse(BaseModel):
    recommendations: list[AIRecommendation] = Field(
        ..., description="Identified operations alerts and customer follow-up actions."
    )


class AICustomerInsightsRequest(BaseModel):
    customer_id: uuid.UUID = Field(..., description="Target customer ID for segmentation and behavior insights.")


class AICustomerInsightsResponse(BaseModel):
    customer_id: uuid.UUID
    insights: str = Field(
        ...,
        description="Behavior analysis, churn likelihood, and personalized action recommendations.",
    )


class PromptTemplateBase(BaseModel):
    name: str = Field(..., description="Unique name/identifier for the prompt template")
    description: str | None = None
    system_prompt: str = Field(..., description="The template content with Jinja-style variables")
    is_active: bool = True


class PromptTemplateCreate(PromptTemplateBase):
    pass


class PromptTemplateUpdate(BaseModel):
    description: str | None = None
    system_prompt: str | None = None
    is_active: bool | None = None


class PromptTemplateResponse(PromptTemplateBase):
    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIMemoryBase(BaseModel):
    context_key: str
    content: str


class AIMemoryCreate(AIMemoryBase):
    pass


class AIMemoryResponse(AIMemoryBase):
    id: uuid.UUID
    business_id: uuid.UUID | None
    user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
