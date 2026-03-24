import jwt
import time
from quart import current_app


def create_token(user_id: str):
    expire_seconds = int(current_app.config.get("JWT_EXPIRE_SECONDS", 7 * 24 * 3600))
    secret = current_app.config.get("JWT_SECRET", "change-me-in-prod")
    algorithm = current_app.config.get("JWT_ALGORITHM", "HS256")
    payload = {
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + expire_seconds,
    }
    return jwt.encode(
        payload,
        secret,
        algorithm=algorithm,
    )


def decode_token(token: str):
    secret = current_app.config.get("JWT_SECRET", "change-me-in-prod")
    algorithm = current_app.config.get("JWT_ALGORITHM", "HS256")
    return jwt.decode(
        token,
        secret,
        algorithms=[algorithm],
    )
