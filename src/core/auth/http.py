import jwt

from functools import wraps
from quart import request, jsonify

from src.infra.shared.jwt import decode_token


def jwt_required(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing token"}), 401

        token = auth.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            request.user = payload["sub"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401

        return await fn(*args, **kwargs)

    return wrapper
