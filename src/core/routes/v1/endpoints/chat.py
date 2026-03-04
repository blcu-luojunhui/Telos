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
            "user_id": "user_001",           // 必填
            "message": "我中午吃了麻辣烫",
            "date": "2025-02-27",            // 可选，默认当天
            "conversation_id": 123           // 可选，不传则复用最近会话或新建
        }

        返回: {
            "user_id": "user_001",
            "conversation_id": 123,           // 本次使用的会话 ID，后续请求可带上
            "type": "saved" | "duplicate_same" | "needs_confirm" | ...,
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

        conv_id = data.get("conversation_id")
        if conv_id is not None:
            try:
                conv_id = int(conv_id)
            except (TypeError, ValueError):
                conv_id = None

        try:
            resp = await handle_chat_message(
                user_id=user_id,
                message=message,
                reference_date=ref_date,
                conversation_id=conv_id,
            )
            return jsonify(
                {
                    "user_id": resp.user_id,
                    "conversation_id": resp.conversation_id,
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
