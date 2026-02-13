from quart import Blueprint, request, jsonify

from src.infra.shared import create_token

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/health")
async def health():
    return {"status": "ok"}


@api_bp.route("/echo", methods=["POST"])
async def echo():
    data = await request.get_json()
    return jsonify(data)


@api_bp.route("/login", methods=["POST"])
async def login():
    data = await request.get_json()
    user_name = data.get("user_name")
    if not user_name:
        return jsonify({"error": "user_name is required"}), 400
    token = create_token(data)
    return jsonify({"token": token}), 200
