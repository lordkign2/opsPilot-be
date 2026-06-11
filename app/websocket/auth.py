"""
OpsPilot — WebSocket Session Authentication.
"""

from __future__ import annotations

from fastapi import WebSocket, status

from app.core.exceptions import OpsPilotException
from app.core.logging import get_logger
from app.db.redis import redis_client
from app.db.session import async_session_factory
from app.modules.auth.models import User, UserRole
from app.modules.auth.service import AuthService

logger = get_logger("websocket.auth")


async def authenticate_websocket(websocket: WebSocket, token: str | None = None) -> User | None:
    """
    Authenticate a WebSocket connection.

    Attempts to extract the JWT token from the query parameters: `?token=...`
    If a token is found and verified, returns the associated active User.
    Otherwise, closes the connection with a WS_1008_POLICY_VIOLATION code.
    """
    client_host = websocket.client.host if websocket.client else "unknown"

    # 1. Try query parameters if not passed explicitly
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        logger.warning("WebSocket handshake rejected from IP %s: Missing token.", client_host)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token.")
        return None

    # 2. Authenticate using AuthService
    async with async_session_factory() as db:
        auth_service = AuthService(db=db, redis=redis_client)

        try:
            user = await auth_service.get_current_user(token)
            if not user.is_active:
                logger.warning(
                    "WebSocket handshake rejected for user %s from IP %s: Inactive account.",
                    user.id,
                    client_host,
                )
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Inactive account.")
                return None
            if not user.business_id and user.role != UserRole.SUPER_ADMIN:
                logger.warning(
                    "WebSocket handshake rejected for user %s from IP %s: No assigned business.",
                    user.id,
                    client_host,
                )
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User has no business assigned.")
                return None

            logger.info(
                "WebSocket connection authenticated successfully for user %s (business: %s) from IP %s",
                user.id,
                user.business_id,
                client_host,
            )
            return user
        except OpsPilotException as e:
            logger.warning(
                "WebSocket handshake rejected from IP %s due to domain exception: %s",
                client_host,
                e.detail,
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=e.detail)
            return None
        except Exception as ex:
            logger.error(
                "Unexpected failure during WebSocket handshake from IP %s: %s",
                client_host,
                ex,
                exc_info=True,
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed.")
            return None
