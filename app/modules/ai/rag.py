"""
OpsPilot — AI Module: Retrieval-Augmented Generation (RAG).

Provides tools for fetching context using pgvector and embeddings.
"""

from __future__ import annotations

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.ai.models import AIMemory

settings = get_settings()

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY.get_secret_value())  # type: ignore


async def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding for the given text using Gemini."""
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set.")

    result = genai.embed_content(  # type: ignore
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]


async def store_memory(
    session: AsyncSession,
    context_key: str,
    content: str,
    business_id: str | None = None,
    user_id: str | None = None,
) -> AIMemory:
    """Store a snippet of text in the AI memory bank with its vector embedding."""
    embedding = await generate_embedding(content)

    memory = AIMemory(
        context_key=context_key,
        content=content,
        embedding=embedding,
        business_id=business_id,
        user_id=user_id,
    )
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    return memory


async def retrieve_relevant_context(
    session: AsyncSession,
    query: str,
    business_id: str | None = None,
    user_id: str | None = None,
    limit: int = 5,
) -> list[AIMemory]:
    """Retrieve the most semantically relevant memories for a given query."""
    if not settings.GEMINI_API_KEY:
        return []

    query_embedding = genai.embed_content(  # type: ignore
        model="models/text-embedding-004",
        content=query,
        task_type="retrieval_query",
    )["embedding"]

    # We use cosine distance: AIMemory.embedding.cosine_distance(query_embedding)
    # Ensure pgvector is used correctly.
    stmt = select(AIMemory)

    if business_id:
        stmt = stmt.where(AIMemory.business_id == business_id)
    if user_id:
        stmt = stmt.where(AIMemory.user_id == user_id)

    stmt = stmt.order_by(AIMemory.embedding.cosine_distance(query_embedding)).limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())
