"""
Chat 接口：带上下文的对话式记录入口。
支持重复检测、确认覆盖/取消流程。
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
            "message": "我中午吃了麻辣烫",
            "session_id": "abc123",   // 可选，首次不传会自动生成
            "date": "2025-02-27"      // 可选，默认当天
        }

        返回: {
            "session_id": "abc123",
            "type": "saved" | "duplicate_same" | "needs_confirm" | "confirmed" | "cancelled" | "error" | "unknown",
            "message": "给用户的自然语言回复",
            "parsed": { ... },
            "saved": { ... },
            "conflict": { ... }
        }
        """
        data = await request.get_json() or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        session_id = data.get("session_id")
        ref_date = None
        if data.get("date"):
            try:
                ref_date = date.fromisoformat(str(data["date"])[:10])
            except (ValueError, TypeError):
                pass

        try:
            resp = await handle_chat_message(
                message=message,
                session_id=session_id,
                reference_date=ref_date,
            )
            return jsonify(
                {
                    "session_id": resp.session_id,
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
