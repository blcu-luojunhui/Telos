"""
NLU 接口：只做自然语言解析，不落库。
"""

from datetime import date

from quart import Blueprint, request, jsonify

from src.domain.interaction import parse_user_message


def create_nlu_bp() -> Blueprint:
    nlu_bp = Blueprint("nlu", __name__, url_prefix="/v1/api")

    @nlu_bp.route("/nlu", methods=["POST"])
    async def nlu():
        """
        Body: { "message": "...", "date": "2025-02-27"(可选) }
        返回解析结果，不写库。
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
            return jsonify(
                {
                    "intent": parsed.intent.value,
                    "date": parsed.date.isoformat() if parsed.date else None,
                    "payload": parsed.payload,
                    "raw_message": parsed.raw_message,
                }
            ), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return nlu_bp
