import jwt

from quart import websocket
from src.infra.shared.jwt import decode_token


async def ws_jwt_auth():
    token = websocket.args.get("token")
    if not token:
        await websocket.close(4001)
        return None

    try:
        payload = decode_token(token)
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        await websocket.close(4002)
    except jwt.InvalidTokenError:
        await websocket.close(4003)

    return None
