"""
Chat 接口：带上下文的对话式记录入口。
基于 user_id 识别用户，支持重复检测、确认覆盖/取消流程。
"""

from datetime import date

from quart import Blueprint, request, jsonify

from src.domain.interaction.chat import handle_chat_message


def create_chat_bp() -> Blueprint:
    chat_bp = Blueprint("chat", __name__, url_prefix="/v1/api")

    @chat_bp.route("/chat", methods=["POST"])
    async def chat():
        """
        Body: {
            "user_id": "user_001",      // 必填
            "message": "我中午吃了麻辣烫",
            "date": "2025-02-27"        // 可选，默认当天
        }

        返回: {
            "user_id": "user_001",
            "type": "saved" | "duplicate_same" | "needs_confirm" | "confirmed" | "cancelled" | "error" | "unknown",
            "message": "给用户的自然语言回复",
            "parsed": { ... },
            "saved": { ... },
            "conflict": { ... }
        }
        """
        data = await request.get_json() or {}

        user_id = (data.get("user_id") or "").strip()
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        ref_date = None
        if data.get("date"):
            try:
                ref_date = date.fromisoformat(str(data["date"])[:10])
            except (ValueError, TypeError):
                import traceback
                print(traceback.format_exc())
                pass
        try:
            resp = await handle_chat_message(
                user_id=user_id,
                message=message,
                reference_date=ref_date,
            )
            return jsonify(
                {
                    "user_id": resp.user_id,
                    "type": resp.type,
                    "message": resp.message,
                    "parsed": resp.parsed,
                    "saved": resp.saved,
                    "conflict": resp.conflict,
                }
            ), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return chat_bp
