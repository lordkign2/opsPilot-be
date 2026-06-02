import logging
from typing import Any, cast

import httpx

from app.core.config import get_settings

logger = logging.getLogger("opspilot.billing.paystack")


class PaystackClient:
    """
    A simple async wrapper for Paystack API.
    Gracefully handles missing API keys for local dev/testing.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = (
            self.settings.PAYSTACK_SECRET_KEY.get_secret_value() if self.settings.PAYSTACK_SECRET_KEY else None
        )
        self.base_url = "https://api.paystack.co"

    def _get_headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def initialize_transaction(self, email: str, amount: int, plan_code: str | None = None) -> dict[str, Any]:
        """
        amount is in kobo.
        """
        if not self.api_key:
            logger.warning("PAYSTACK_SECRET_KEY not set. Simulating transaction initialization.")
            return {
                "status": True,
                "message": "Simulated initialization",
                "data": {
                    "authorization_url": "https://checkout.paystack.com/mock-simulated-url",
                    "access_code": "mock_access_code",
                    "reference": "mock_ref_" + str(amount),
                },
            }

        payload = {
            "email": email,
            "amount": amount,
        }
        if plan_code:
            payload["plan"] = plan_code

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/transaction/initialize", json=payload, headers=self._get_headers(), timeout=10.0
                )
                resp.raise_for_status()
                return cast(dict[str, Any], resp.json())
            except Exception as e:
                logger.error("Failed to initialize Paystack transaction: %s", str(e))
                raise

    async def verify_transaction(self, reference: str) -> dict[str, Any]:
        if not self.api_key:
            logger.warning("PAYSTACK_SECRET_KEY not set. Simulating transaction verification.")
            return {
                "status": True,
                "message": "Simulated verification",
                "data": {
                    "status": "success",
                    "reference": reference,
                    "amount": 10000,
                    "customer": {"email": "test@example.com"},
                },
            }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/transaction/verify/{reference}", headers=self._get_headers(), timeout=10.0
                )
                resp.raise_for_status()
                return cast(dict[str, Any], resp.json())
            except Exception as e:
                logger.error("Failed to verify Paystack transaction %s: %s", reference, str(e))
                raise
