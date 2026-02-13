from quart import Blueprint, websocket
import asyncio

ws_bp = Blueprint("ws", __name__, url_prefix="/ws")


@ws_bp.websocket("/chat")
async def chat():
    while True:
        msg = await websocket.receive()
        await asyncio.sleep(0.1)
        await websocket.send(f"echo: {msg}")
