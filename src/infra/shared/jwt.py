import jwt
import time
from quart import current_app


def create_token(user_id: str):
    payload = {
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + current_app.config["JWT_EXPIRE_SECONDS"],
    }
    return jwt.encode(
        payload,
        current_app.config["JWT_SECRET"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def decode_token(token: str):
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )
