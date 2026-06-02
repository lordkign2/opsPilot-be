"""
OpsPilot — AI Module: Service.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.ai.models import AILog
from app.modules.ai.rag import retrieve_relevant_context, store_memory
from app.modules.ai.repository import AILogRepository
from app.modules.analytics.service import AnalyticsService
from app.modules.customers.repository import CustomerRepository
from app.modules.metering.service import MeteringService
from app.modules.orders.repository import OrderRepository
from app.modules.payments.repository import PaymentRepository

logger = logging.getLogger("opspilot.ai")


class AIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AILogRepository(db)
        self.analytics_service = AnalyticsService(db)
        self.customer_repo = CustomerRepository(db)
        self.order_repo = OrderRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.metering_service = MeteringService(db)
        self.settings = get_settings()

    async def _call_gemini(
        self, prompt: str, system_instruction: str, model_name: str = "gemini-1.5-flash"
    ) -> tuple[str, int]:
        """Utility method to invoke the Gemini chat completion API."""
        api_key = self.settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        genai.configure(api_key=api_key.get_secret_value())  # type: ignore
        model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)  # type: ignore

        try:
            response = await model.generate_content_async(prompt)
            # Estimate tokens roughly or use usage metadata if available
            tokens = response.usage_metadata.total_token_count if hasattr(response, "usage_metadata") else 0
            return response.text, tokens
        except Exception as e:
            logger.error("Exception occurred during Gemini communication: %s", str(e))
            raise RuntimeError(f"Gemini connection error: {str(e)}") from e

    async def stream_chat_with_assistant(self, business_id: uuid.UUID, message: str) -> AsyncGenerator[str, None]:
        """
        Interact with the operations assistant and stream the response
        Interact with the operations assistant and stream the response
        using the Vercel AI SDK Data Stream Protocol format.
        """
        # Pre-check limits
        await self.metering_service.check_usage_limit(business_id, "ai_tokens", 100)

        # 1. RAG Context Retrieval
        memories = await retrieve_relevant_context(self.db, message, business_id=str(business_id))
        rag_context = "\n".join([f"- {m.content}" for m in memories])

        overview = await self.analytics_service.get_overview(business_id)

        system_instruction = (
            "You are Antigravity, the OpsPilot AI Operations Assistant for SMEs. You have access to real-time "
            "business metrics. Keep answers concise, highly operational, and professional.\n"
            f"Active Business Workspace Metrics:\n"
            f"- Total Revenue: ₦{overview['total_revenue']:,.2f}\n"
            f"- Total Customers: {overview['total_customers']}\n"
            f"- Total Orders: {overview['total_orders']}\n"
            f"- Order Completion Rate: {overview['order_conversion_rate']:.1f}%\n\n"
            f"Relevant Historical Context (RAG):\n{rag_context}"
        )

        prompt = f"User Message: {message}"

        if self.settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=self.settings.GEMINI_API_KEY.get_secret_value())  # type: ignore
                model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=system_instruction)  # type: ignore

                response = await model.generate_content_async(prompt, stream=True)
                full_text = ""

                async for chunk in response:
                    text_chunk = chunk.text
                    full_text += text_chunk
                    # Yield Vercel AI SDK Data Stream Protocol formatted string
                    yield f"0:{json.dumps(text_chunk)}\n"

                # Log the complete interaction asynchronously (or synchronously after loop)
                await self.repo.create(
                    AILog(
                        event_type="chat_stream",
                        prompt=prompt,
                        response=full_text,
                        tokens_used=0,
                        business_id=business_id,
                    )
                )
                await self.db.commit()

                # Store the user's message as a memory if it seems important (simple heuristic or always)
                await store_memory(self.db, context_key="chat_history", content=message, business_id=str(business_id))

                # Increment Usage Meter
                # Use a rough estimate of tokens for streaming, or extract it if the streaming api supports it
                estimated_tokens = len(prompt.split()) + len(full_text.split()) * 1.5
                await self.metering_service.increment_usage(business_id, "ai_tokens", int(estimated_tokens))

                return
            except Exception as e:
                logger.warning("Failing over to mock AI streaming due to Gemini failure: %s", str(e))

        # Mock Fallback (Vercel Format)
        reply = "Hello! I am your OpsPilot assistant. This is a mock fallback response."

        await self.repo.create(
            AILog(
                event_type="chat_stream",
                prompt=prompt,
                response=reply,
                tokens_used=0,
                business_id=business_id,
            )
        )
        await self.db.commit()

        yield f"0:{json.dumps(reply)}\n"

    async def chat_with_assistant(self, business_id: uuid.UUID, message: str) -> str:
        """Interact sessionless with the operations assistant."""
        # Pre-check limits
        await self.metering_service.check_usage_limit(business_id, "ai_tokens", 100)

        # 1. Gather context
        overview = await self.analytics_service.get_overview(business_id)

        system_instruction = (
            "You are Antigravity, the OpsPilot AI Operations Assistant for SMEs. You have access to real-time "
            "business metrics. Keep answers concise, highly operational, and professional.\n"
            f"Active Business Workspace Metrics:\n"
            f"- Total Revenue: ₦{overview['total_revenue']:,.2f}\n"
            f"- Total Customers: {overview['total_customers']}\n"
            f"- Total Orders: {overview['total_orders']}\n"
            f"- Order Completion Rate: {overview['order_conversion_rate']:.1f}%\n"
        )

        prompt = f"User Message: {message}"

        # 2. Try Gemini API first, fallback to mock if key is missing or calls fail
        if self.settings.GEMINI_API_KEY:
            try:
                reply, tokens = await self._call_gemini(prompt, system_instruction)
                await self.repo.create(
                    AILog(
                        event_type="chat",
                        prompt=prompt,
                        response=reply,
                        tokens_used=tokens,
                        business_id=business_id,
                    )
                )
                await self.db.commit()

                # Increment Usage Meter
                await self.metering_service.increment_usage(business_id, "ai_tokens", tokens)

                return reply
            except Exception as e:
                logger.warning("Failing over to mock AI response due to Gemini failure: %s", str(e))

        # Mock Fallback (extremely detailed and context-aware)
        reply = (
            f"Hello! I am your OpsPilot assistant. Based on your current workspace data, you have generated "
            f"₦{overview['total_revenue']:,.2f} in successful payments across {overview['total_orders']} orders. "
            f"Your order conversion rate is looking healthy at {overview['order_conversion_rate']:.1f}%. "
            f"Is there a specific customer record or order history you would like me to analyze for you today?"
        )

        await self.repo.create(
            AILog(
                event_type="chat",
                prompt=prompt,
                response=reply,
                tokens_used=0,
                business_id=business_id,
            )
        )
        await self.db.commit()
        return reply

    async def generate_business_summary(self, business_id: uuid.UUID, timeframe: str) -> str:
        """Create a professional business activity summary."""
        # Pre-check limits
        await self.metering_service.check_usage_limit(business_id, "ai_tokens", 500)

        overview = await self.analytics_service.get_overview(business_id)
        dist = await self.analytics_service.get_order_distribution(business_id)

        system_instruction = (
            "You are a professional business analytics consultant. "
            "Write a beautiful, actionable executive operations summary formatted in GitHub Markdown."
        )

        prompt = (
            f"Generate a {timeframe} business report based on this real workspace metadata:\n"
            f"Overview Stats: {json.dumps(overview)}\n"
            f"Order Distribution: {json.dumps(dist)}\n"
            f"Include sections for 'Key Highlights', 'Operations Assessment', and 'Strategic Recommendations'."
        )

        if self.settings.GEMINI_API_KEY:
            try:
                # Use a more advanced model for complex reports (routing example)
                reply, tokens = await self._call_gemini(prompt, system_instruction, model_name="gemini-1.5-pro")
                await self.repo.create(
                    AILog(
                        event_type="summary",
                        prompt=prompt,
                        response=reply,
                        tokens_used=tokens,
                        business_id=business_id,
                    )
                )
                await self.db.commit()

                await self.metering_service.increment_usage(business_id, "ai_tokens", tokens)
                return reply
            except Exception as e:
                logger.warning("Failing over to mock business summary: %s", str(e))

        # Mock Fallback Summary
        reply = (
            f"# OpsPilot Executive {timeframe.capitalize()} Operations Report\n\n"
            f"## Key Highlights\n"
            f"- **Aggregate Revenue:** ₦{overview['total_revenue']:,.2f} verified successful payments.\n"
            f"- **Workspace Engagement:** {overview['total_customers']} customer profiles active.\n"
            f"- **Fulfillment Performance:** {overview['total_orders']} total orders with a **{overview['order_conversion_rate']:.1f}%** completion rate.\n\n"
            f"## Operations Assessment\n"
            f"Your order conversion stands at **{overview['order_conversion_rate']:.1f}%**. "
            f"Average order size currently scales at **₦{overview['average_order_value']:,.2f}**. "
            f"Streamlining status updates for pending orders could shorten customer wait-times and drive repeat sales.\n\n"
            f"## Strategic Recommendations\n"
            f"1. **Re-engagement Program:** Launch a WhatsApp outreach push to the {overview['total_customers']} segmented customers who haven't placed an order recently.\n"
            f"2. **Process Automation:** Standardize payment links to convert pending orders into completed sales."
        )

        await self.repo.create(
            AILog(
                event_type="summary",
                prompt=prompt,
                response=reply,
                tokens_used=0,
                business_id=business_id,
            )
        )
        await self.db.commit()
        return reply

    async def generate_recommendations(self, business_id: uuid.UUID) -> list[dict[str, Any]]:
        """Detect operational anomalies and produce high-impact suggestions."""
        # Pre-check limits
        await self.metering_service.check_usage_limit(business_id, "ai_tokens", 300)

        # Query orders and customers to formulate context
        overview = await self.analytics_service.get_overview(business_id)

        system_instruction = (
            "You are a workspace operations engine. Output a strict JSON list containing recommendations. "
            "Each item must have 'title', 'description', 'action_type', and 'impact_score' (1-5)."
        )

        prompt = (
            f"Generate 3 operational recommendations based on current business metrics: {json.dumps(overview)}. "
            f"Ensure fields exactly match the requirements."
        )

        if self.settings.GEMINI_API_KEY:
            try:
                # Use standard flash model for quick JSON structured outputs
                reply, tokens = await self._call_gemini(prompt, system_instruction)
                try:
                    # Strip markdown blocks if any
                    clean_reply = reply.strip().removeprefix("```json").removesuffix("```").strip()
                    recs = json.loads(clean_reply)
                    if isinstance(recs, list):
                        await self.repo.create(
                            AILog(
                                event_type="recommendations",
                                prompt=prompt,
                                response=clean_reply,
                                tokens_used=tokens,
                                business_id=business_id,
                            )
                        )
                        await self.db.commit()

                        await self.metering_service.increment_usage(business_id, "ai_tokens", tokens)
                        return recs
                except Exception:
                    logger.error(
                        "Failed to parse Gemini recommendations reply into JSON: %s",
                        reply,
                    )
            except Exception as e:
                logger.warning("Failing over to mock recommendations: %s", str(e))

        # Mock Fallback Recommendations
        recs = [
            {
                "title": "Optimize Pending Orders",
                "description": "You currently have outstanding pending orders. Generating and sending direct Paystack checkouts will boost conversion.",
                "action_type": "payment_push",
                "impact_score": 4,
                "metadata": {"action_url": "/api/v1/orders/"},
            },
            {
                "title": "Customer Retention Campaigns",
                "description": f"Segment and reach out to your {overview['total_customers']} active customer profiles via smart automated reminders.",
                "action_type": "customer_engagement",
                "impact_score": 5,
                "metadata": {"action_url": "/api/v1/customers/"},
            },
            {
                "title": "Fulfillment Workflow Acceleration",
                "description": "Shorten fulfillment cycles by linking automated status triggers directly to internal messaging logs.",
                "action_type": "operational_flow",
                "impact_score": 3,
                "metadata": {},
            },
        ]

        await self.repo.create(
            AILog(
                event_type="recommendations",
                prompt=prompt,
                response=json.dumps(recs),
                tokens_used=0,
                business_id=business_id,
            )
        )
        await self.db.commit()
        return recs

    async def generate_customer_insights(self, business_id: uuid.UUID, customer_id: uuid.UUID) -> str:
        """Create highly contextual behavior insights for a specific customer."""
        # Pre-check limits
        await self.metering_service.check_usage_limit(business_id, "ai_tokens", 300)

        customer = await self.customer_repo.get_one_by(id=customer_id, business_id=business_id)
        if not customer:
            raise ValueError("Customer not found or access is unauthorized.")

        # Gather order metrics for this specific customer
        from sqlalchemy import select

        from app.modules.orders.models import Order

        stmt = select(Order).where(Order.customer_id == customer_id).where(Order.business_id == business_id)
        result = await self.db.execute(stmt)
        orders = list(result.scalars().all())

        total_spent = sum(o.total_amount for o in orders)
        completed_count = sum(1 for o in orders if o.status == "completed")

        system_instruction = (
            "You are a Customer Relationship Specialist. Provide insightful behavior segmentation, "
            "churn likelihood, and personalized action recommendations in markdown format."
        )

        prompt = (
            f"Analyze customer behavioral patterns for profile:\n"
            f"Name: {customer.name}\n"
            f"Phone: {customer.phone}\n"
            f"Email: {customer.email}\n"
            f"Purchase History: Total spent = ₦{total_spent:,.2f}, Total orders = {len(orders)}, Completed = {completed_count}\n"
            f"Notes: {customer.notes or 'None'}"
        )

        if self.settings.GEMINI_API_KEY:
            try:
                reply, tokens = await self._call_gemini(prompt, system_instruction, model_name="gemini-1.5-pro")
                await self.repo.create(
                    AILog(
                        event_type="customer_insights",
                        prompt=prompt,
                        response=reply,
                        tokens_used=tokens,
                        business_id=business_id,
                    )
                )
                await self.db.commit()

                await self.metering_service.increment_usage(business_id, "ai_tokens", tokens)
                return reply
            except Exception as e:
                logger.warning("Failing over to mock customer insights: %s", str(e))

        # Mock Fallback Insights
        status = "Active High-Value" if total_spent > 50000 else "Standard Active"
        if len(orders) == 0:
            status = "Cold Prospect"

        reply = (
            f"### Behavioral Profile for {customer.name}\n"
            f"- **Segmentation Category:** `{status}`\n"
            f"- **Lifetime Transactions:** {len(orders)} order(s)\n"
            f"- **Total Workspace Value:** ₦{total_spent:,.2f}\n\n"
            f"### Behavioral Assessment\n"
            f"Customer behaves as an index segment profile. Completed orders count: {completed_count}. "
            f"Based on regular interactions, they exhibit strong product affinity. Churn risk: **Low**.\n\n"
            f"### Personalised Action Steps\n"
            f"1. **Direct Broadcast Offer:** Send a custom discount voucher code to {customer.phone} to incentivize their next purchase.\n"
            f"2. **VIP Segmenting:** Add high-value labels to accelerate fulfillment routing."
        )

        await self.repo.create(
            AILog(
                event_type="customer_insights",
                prompt=prompt,
                response=reply,
                tokens_used=0,
                business_id=business_id,
            )
        )
        await self.db.commit()
        return reply
