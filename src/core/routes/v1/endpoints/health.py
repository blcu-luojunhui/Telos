from __future__ import annotations

from quart import Blueprint, jsonify


def create_health_bp() -> Blueprint:
    health_bp = Blueprint("health", __name__, url_prefix="/v1/api")

    @health_bp.route("/health", methods=["GET"])
    async def health():
        return jsonify(
            {"code": 0, "message": "success", "data": {"message": "hello world"}}
        )

    return health_bp
