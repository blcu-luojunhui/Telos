"""
Record 接口：接收已解析的结构化数据，直接落库。
"""

from datetime import date

from quart import Blueprint, request, jsonify

from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.domain.interaction import apply_parsed_record


def create_record_bp() -> Blueprint:
    record_bp = Blueprint("record", __name__, url_prefix="/v1/api")

    @record_bp.route("/record", methods=["POST"])
    async def record():
        """
        Body: {
            "intent": "record_meal",
            "date": "2025-02-27",   // 可选，默认当天
            "payload": { ... }
        }
        """
        data = await request.get_json() or {}
        intent_str = (data.get("intent") or "").strip().lower()
        if not intent_str:
            return jsonify({"error": "intent is required"}), 400

        try:
            intent = IntentType(intent_str)
        except ValueError:
            return jsonify({"error": f"unknown intent: {intent_str}"}), 400

        ref_date = date.today()
        if data.get("date"):
            try:
                ref_date = date.fromisoformat(str(data["date"])[:10])
            except (ValueError, TypeError):
                pass

        parsed = ParsedRecord(
            intent=intent,
            date=ref_date,
            payload=data.get("payload") or {},
            raw_message=data.get("raw_message", ""),
        )

        try:
            result = await apply_parsed_record(parsed)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return record_bp
