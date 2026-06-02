"""
OpsPilot — AI Background Tasks.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger("opspilot.tasks.ai")


async def generate_ai_insight_task(ctx: dict[str, Any], business_id: str, data_payload: dict[str, Any]) -> str:
    """
    Generate an AI insight in the background.
    This simulates offloading a heavy LLM call.
    """
    logger.info(f"Starting AI insight generation for business {business_id}...")
    await asyncio.sleep(2)  # Simulate LLM delay
    logger.info(f"Finished AI insight generation for business {business_id}.")
    return "Insight generated successfully."
