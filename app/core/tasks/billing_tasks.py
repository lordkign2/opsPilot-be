"""
OpsPilot — Billing Background Tasks.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger("opspilot.tasks.billing")


async def process_paystack_webhook_task(ctx: dict[str, Any], event_payload: dict[str, Any]) -> str:
    """
    Process a Paystack webhook in the background so the API returns 200 OK instantly.
    """
    logger.info("Processing Paystack webhook asynchronously...")
    await asyncio.sleep(1)  # Simulate DB/API work
    logger.info("Webhook processed.")
    return "Webhook processed."
