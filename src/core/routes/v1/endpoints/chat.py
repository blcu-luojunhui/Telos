"""
Chat 接口：带上下文的对话式记录入口。
基于 user_id 识别用户，支持重复检测、确认覆盖/取消流程。
"""

from datetime import date

from quart import Blueprint, request, jsonify, current_app


def create_chat_bp() -> Blueprint:
    chat_bp = Blueprint("chat", __name__, url_prefix="/v1/api")

    @chat_bp.route("/chat/history", methods=["GET"])
    async def chat_history():
        """
        拉取会话历史，后端为唯一真相源。
        Query: user_id（必填）, conversation_id（可选，不传则取该用户最近一次会话）
        返回: { "conversation_id": number | null, "messages": [ { "role", "content", "msg_type", "sticker_id"? } ] }
        """
        user_id = (request.args.get("user_id") or "").strip()
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        conv_id_param = request.args.get("conversation_id")
        conv_id = None
        if conv_id_param is not None and conv_id_param != "":
            try:
                conv_id = int(conv_id_param)
            except (TypeError, ValueError):
                conv_id = None
        svc = current_app.chat_service
        if conv_id is None:
            conv_id = await svc.get_latest_conversation_id(user_id)
        else:
            if not await svc.conversation_belongs_to_user(user_id, conv_id):
                return jsonify({"conversation_id": None, "messages": []}), 200
        if conv_id is None:
            return jsonify({"conversation_id": None, "messages": []}), 200
        session = svc.get_user_session(user_id, conv_id)
        history = await session.get_recent_history(limit=100)
        messages = []
        for h in history:
            extra = h.get("extra") or {}
            sticker_id = extra.get("sticker_id")
            messages.append({
                "role": h["role"],
                "content": h["content"],
                "msg_type": h.get("msg_type"),
                **({"sticker_id": sticker_id} if sticker_id is not None else {}),
            })
        return jsonify({"conversation_id": conv_id, "messages": messages}), 200

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
            resp = await current_app.chat_service.handle_chat_message(
                user_id=user_id,
                message=message,
                reference_date=ref_date,
                conversation_id=conv_id,
            )
            out = {
                "user_id": resp.user_id,
                "conversation_id": resp.conversation_id,
                "type": resp.type,
                "message": resp.message,
                "parsed": resp.parsed,
                "saved": resp.saved,
                "conflict": resp.conflict,
            }
            if getattr(resp, "sticker_id", None) is not None:
                out["sticker_id"] = resp.sticker_id
            return jsonify(out), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return chat_bp
