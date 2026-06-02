"""
OpsPilot — AI Module: Routes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.ai.dependencies import AIServiceDep
from app.modules.ai.models import PromptTemplate
from app.modules.ai.schemas import (
    AIChatRequest,
    AICustomerInsightsRequest,
    AICustomerInsightsResponse,
    AIRecommendationsResponse,
    AISummaryRequest,
    AISummaryResponse,
    PromptTemplateCreate,
    PromptTemplateResponse,
)
from app.modules.auth.dependencies import CurrentBusinessId
from app.shared.response import success_response

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/chat", response_class=StreamingResponse)
async def chat_with_assistant(
    payload: AIChatRequest,
    business_id: CurrentBusinessId,
    ai_service: AIServiceDep,
) -> StreamingResponse:
    """
    Interact with the AI business assistant using the Vercel AI SDK Data Stream Protocol.
    """
    generator = ai_service.stream_chat_with_assistant(business_id, payload.message)

    return StreamingResponse(generator, media_type="text/plain", headers={"x-vercel-ai-data-stream": "v1"})


@router.post("/prompts", response_model=PromptTemplateResponse)
async def create_prompt_template(
    payload: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new prompt template."""
    prompt = PromptTemplate(**payload.model_dump())
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.get("/prompts", response_model=list[PromptTemplateResponse])
async def get_prompt_templates(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve all prompt templates."""
    stmt = select(PromptTemplate).order_by(PromptTemplate.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/summary", response_model=None)
async def generate_business_summary(
    payload: AISummaryRequest,
    business_id: CurrentBusinessId,
    ai_service: AIServiceDep,
) -> Any:
    """Generate professional workspace performance summaries."""
    summary = await ai_service.generate_business_summary(business_id, payload.timeframe)
    return success_response(
        data=AISummaryResponse(summary=summary).model_dump(),
        message="Operations summary generated successfully.",
    )


@router.post("/recommendations", response_model=None)
async def generate_recommendations(
    business_id: CurrentBusinessId,
    ai_service: AIServiceDep,
) -> Any:
    """Get operational optimization recommendations."""
    recs = await ai_service.generate_recommendations(business_id)
    return success_response(
        data=AIRecommendationsResponse(recommendations=recs).model_dump(),
        message="Operational recommendations compiled successfully.",
    )


@router.post("/customer-insights", response_model=None)
async def generate_customer_insights(
    payload: AICustomerInsightsRequest,
    business_id: CurrentBusinessId,
    ai_service: AIServiceDep,
) -> Any:
    """Analyze behavior segmentation and churn likelihood for a specific customer."""
    insights = await ai_service.generate_customer_insights(business_id, payload.customer_id)
    return success_response(
        data=AICustomerInsightsResponse(customer_id=payload.customer_id, insights=insights).model_dump(),
        message="Customer behavioral insights compiled successfully.",
    )
