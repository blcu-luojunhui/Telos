from datetime import date

from quart import Blueprint, request, jsonify

from src.domain.interaction import parse_user_message, apply_parsed_record


def create_record_bp():

    record_bp = Blueprint("record", __name__, url_prefix="/v1/api")

    @record_bp.route("/record", methods=["POST"])
    async def record():
        """
        接收自然语言输入，解析意图并落表。
        Body: { "message": "今天中午吃了牛肉面，挺饱的", "date": "2025-02-27" }（date 可选，默认当天）
        """
        import traceback
        data = await request.get_json() or {}
        message = (data.get("message") or "").strip()
        print(message)
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
            return jsonify(
                {
                    "parsed": {
                        "intent": parsed.intent.value,
                        "date": parsed.date.isoformat() if parsed.date else None,
                        "payload": parsed.payload,
                    },
                    "saved": result,
                }
            ), 200
        except ValueError as e:
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    return record_bp