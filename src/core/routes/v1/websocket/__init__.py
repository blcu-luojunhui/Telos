from quart import Blueprint, websocket
import asyncio

from src.core.routes.auth import ws_jwt_auth

ws_bp = Blueprint("ws", __name__, url_prefix="/ws")


@ws_bp.websocket("/chat")
async def chat():
    user_id = await ws_jwt_auth()
    if not user_id:
        return
    while True:
        msg = await websocket.receive()
        await asyncio.sleep(0.1)
        await websocket.send(f"echo({user_id}): {msg}")
