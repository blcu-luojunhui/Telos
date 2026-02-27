from datetime import date

from quart import Blueprint, request, jsonify

from src.infra.shared import create_token
from src.core.interaction import parse_user_message, apply_parsed_record

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


@api_bp.route("/record", methods=["POST"])
async def record():
    """
    接收自然语言输入，解析意图并落表。
    Body: { "message": "今天中午吃了牛肉面，挺饱的", "date": "2025-02-27" }（date 可选，默认当天）
    """
    data = await request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    ref_date = None
    if data.get("date"):
        try:
            ref_date = date.fromisoformat(str(data["date"])[:10])
        except (ValueError, TypeError):
            pass
    try:
        parsed = await parse_user_message(message, reference_date=ref_date)
        result = await apply_parsed_record(parsed)
        return jsonify({
            "parsed": {
                "intent": parsed.intent.value,
                "date": parsed.date.isoformat() if parsed.date else None,
                "payload": parsed.payload,
            },
            "saved": result,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
