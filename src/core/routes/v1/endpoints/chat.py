"""
Chat 接口：带上下文的对话式记录入口。
基于 user_id 识别用户，支持重复检测、确认覆盖/取消流程。
"""

from datetime import date

from quart import Blueprint, request, jsonify, current_app
from sqlalchemy import select, desc, func, update, delete, or_, case

from src.core.audit import new_trace_id
from src.core.routes.auth import jwt_required
from src.infra.persistence.mysql_soul_repository import (
    list_souls_from_db,
    seed_souls_if_empty,
)
from src.infra.database.mysql import async_mysql_pool, Conversation, ChatMessage


def create_chat_bp() -> Blueprint:
    chat_bp = Blueprint("chat", __name__, url_prefix="/v1/api")

    @chat_bp.route("/souls", methods=["GET"])
    async def souls_list():
        """
        返回可选 Agent 人格列表（来自 souls 表），供前端展示为筛选按钮。
        若表为空会先种子写入默认人格。
        返回: { "souls": [ { "id", "slug", "name", "description" }, ... ] }
        """
        await seed_souls_if_empty()
        souls = await list_souls_from_db()
        return jsonify({"souls": souls}), 200

    @chat_bp.route("/chat/history", methods=["GET"])
    @jwt_required
    async def chat_history():
        """
        拉取会话历史，后端为唯一真相源。
        Query: user_id（必填）, conversation_id（可选，不传则取该用户最近一次会话）
        返回: { "conversation_id": number | null, "messages": [ { "role", "content", "msg_type", "sticker_id"? } ] }
        """
        # user_id 优先取自 JWT，其次才读 query 参数，保证后端以 token 为准
        token_user = getattr(request, "user", None)
        user_id = (request.args.get("user_id") or "").strip()
        if token_user:
            user_id = str(token_user).strip()
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
            msg_item = {
                "role": h["role"],
                "content": h["content"],
                "msg_type": h.get("msg_type"),
                **({"sticker_id": sticker_id} if sticker_id is not None else {}),
            }
            if isinstance(extra, dict) and (
                extra.get("plan_preview") is not None
                or extra.get("plan_requires_confirm") is not None
            ):
                msg_item["extra"] = {
                    "plan_preview": extra.get("plan_preview"),
                    "plan_requires_confirm": bool(extra.get("plan_requires_confirm")),
                    **({"plan_id": extra.get("plan_id")} if extra.get("plan_id") is not None else {}),
                }
            if h.get("soul_id") is not None:
                msg_item["soul_id"] = h["soul_id"]
            if h.get("soul"):
                msg_item["soul"] = h["soul"]
            messages.append(msg_item)
        return jsonify({"conversation_id": conv_id, "messages": messages}), 200

    @chat_bp.route("/chat/conversations", methods=["GET"])
    @jwt_required
    async def chat_conversations():
        """
        拉取用户会话列表（按最近更新时间倒序），供前端会话管理使用。
        返回: { "conversations": [ { conversation_id, title, preview, status, updated_at } ] }
        """
        token_user = getattr(request, "user", None)
        user_id = (request.args.get("user_id") or "").strip()
        if token_user:
            user_id = str(token_user).strip()
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        limit = 30
        limit_param = request.args.get("limit")
        if limit_param:
            try:
                limit = max(1, min(int(limit_param), 100))
            except (TypeError, ValueError):
                limit = 30

        async with async_mysql_pool.session() as session:
            last_msg_subq = (
                select(
                    ChatMessage.conversation_id.label("conversation_id"),
                    func.max(ChatMessage.id).label("last_msg_id"),
                )
                .where(
                    ChatMessage.user_id == user_id,
                    ChatMessage.conversation_id.is_not(None),
                )
                .group_by(ChatMessage.conversation_id)
                .subquery()
            )
            stmt = (
                select(
                    Conversation.id,
                    Conversation.title,
                    Conversation.status,
                    Conversation.updated_at,
                    ChatMessage.content.label("last_content"),
                )
                .where(
                    Conversation.user_id == user_id,
                    or_(Conversation.status == "active", Conversation.status == "pinned"),
                )
                .outerjoin(
                    last_msg_subq,
                    last_msg_subq.c.conversation_id == Conversation.id,
                )
                .outerjoin(ChatMessage, ChatMessage.id == last_msg_subq.c.last_msg_id)
                .order_by(
                    desc(case((Conversation.status == "pinned", 1), else_=0)),
                    desc(Conversation.updated_at),
                    desc(Conversation.id),
                )
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()

        conversations = []
        for row in rows:
            preview = (row.last_content or "").strip()
            auto_title = preview[:24] + ("..." if len(preview) > 24 else "")
            title = (row.title or "").strip() or auto_title or f"会话 {row.id}"
            conversations.append(
                {
                    "conversation_id": int(row.id),
                    "title": title,
                    "preview": preview[:80],
                    "status": row.status,
                    "pinned": row.status == "pinned",
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
            )

        return jsonify({"conversations": conversations}), 200

    @chat_bp.route("/chat/conversations", methods=["POST"])
    @jwt_required
    async def create_conversation():
        """
        显式新建会话（用于前端点击“新建会话”时立即落库并返回 ID）。
        Body: { "title"?: str }
        """
        token_user = getattr(request, "user", None)
        user_id = str(token_user or "").strip()
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        data = await request.get_json() or {}
        title = str(data.get("title") or "").strip()
        title = title[:255] if title else None

        async with async_mysql_pool.session() as session:
            conv = Conversation(user_id=user_id, title=title, status="active")
            session.add(conv)
            await session.commit()
            await session.refresh(conv)

        return jsonify(
            {
                "conversation_id": int(conv.id),
                "title": conv.title,
                "status": conv.status,
                "pinned": False,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
        ), 201

    @chat_bp.route("/chat/conversations/<int:conversation_id>", methods=["PATCH"])
    @jwt_required
    async def update_conversation(conversation_id: int):
        """
        更新会话信息：支持重命名 title、置顶/取消置顶 pinned。
        Body: { "title"?: str, "pinned"?: bool }
        """
        token_user = getattr(request, "user", None)
        user_id = str(token_user or "").strip()
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        data = await request.get_json() or {}
        title_in = data.get("title")
        pinned_in = data.get("pinned")
        if title_in is None and pinned_in is None:
            return jsonify({"error": "nothing to update"}), 400

        values = {}
        if title_in is not None:
            title = str(title_in).strip()
            values["title"] = title[:255] if title else None
        if pinned_in is not None:
            values["status"] = "pinned" if bool(pinned_in) else "active"

        async with async_mysql_pool.session() as session:
            stmt = (
                update(Conversation)
                .where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
                .values(**values)
            )
            result = await session.execute(stmt)
            if result.rowcount == 0:
                await session.rollback()
                return jsonify({"error": "conversation not found"}), 404
            await session.commit()

            row_stmt = (
                select(Conversation.id, Conversation.title, Conversation.status, Conversation.updated_at)
                .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
                .limit(1)
            )
            row = (await session.execute(row_stmt)).first()

        return jsonify(
            {
                "conversation_id": int(row.id),
                "title": row.title,
                "status": row.status,
                "pinned": row.status == "pinned",
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        ), 200

    @chat_bp.route("/chat/conversations/<int:conversation_id>", methods=["DELETE"])
    @jwt_required
    async def delete_conversation(conversation_id: int):
        """
        删除会话（软删除）：将状态置为 archived，并清除 pending。
        """
        token_user = getattr(request, "user", None)
        user_id = str(token_user or "").strip()
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        async with async_mysql_pool.session() as session:
            upd = (
                update(Conversation)
                .where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
                .values(status="archived")
            )
            result = await session.execute(upd)
            if result.rowcount == 0:
                await session.rollback()
                return jsonify({"error": "conversation not found"}), 404

            await session.execute(
                delete(ChatMessage).where(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.user_id == user_id,
                )
            )
            await session.commit()

        return jsonify({"ok": True, "conversation_id": conversation_id}), 200

    @chat_bp.route("/chat", methods=["POST"])
    @jwt_required
    async def chat():
        """
        Body: {
            "user_id": "user_001",           // 必填
            "message": "我中午吃了麻辣烫",
            "date": "2025-02-27",            // 可选，默认当天
            "conversation_id": 123,          // 可选，不传则复用最近会话或新建
            "soul_id": "rude"                // 可选，Agent 人格 id（见 GET /souls），不传用默认
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

        # user_id 优先取自 JWT，其次才读 body，保持向后兼容
        token_user = getattr(request, "user", None)
        user_id = (data.get("user_id") or "").strip()
        if token_user:
            user_id = str(token_user).strip()
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
                current_app.logger.info("Invalid date in /chat: %r", data.get("date"))

        conv_id = data.get("conversation_id")
        if conv_id is not None:
            try:
                conv_id = int(conv_id)
            except (TypeError, ValueError):
                conv_id = None

        soul_id = (data.get("soul_id") or "").strip() or None

        trace_id = request.headers.get("X-Trace-ID") or new_trace_id()
        try:
            resp = await current_app.chat_service.handle_chat_message(
                user_id=user_id,
                message=message,
                reference_date=ref_date,
                conversation_id=conv_id,
                trace_id=trace_id,
                soul_id=soul_id,
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
            if getattr(resp, "trace_id", None):
                out["trace_id"] = resp.trace_id
            if getattr(resp, "extra", None) and isinstance(resp.extra, dict):
                out["extra"] = resp.extra

            # 将 LLM token 使用与预估费用一并返回，便于前端/调用方做成本监控。
            llm_metrics = None
            if getattr(resp, "extra", None) and isinstance(resp.extra, dict):
                llm_metrics = resp.extra.get("llm_metrics")
            if isinstance(llm_metrics, dict) and llm_metrics:
                total_tokens = 0
                prompt_tokens = 0
                completion_tokens = 0
                estimated_cost_usd = 0.0
                for m in llm_metrics.values():
                    if not isinstance(m, dict):
                        continue
                    total_tokens += int(m.get("total_tokens", 0) or 0)
                    prompt_tokens += int(m.get("prompt_tokens", 0) or 0)
                    completion_tokens += int(m.get("completion_tokens", 0) or 0)
                    try:
                        estimated_cost_usd += float(m.get("estimated_cost_usd") or 0.0)
                    except (TypeError, ValueError):
                        pass
                out["llm_usage"] = {
                    "total_tokens": total_tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
                out["llm_cost_usd"] = round(estimated_cost_usd, 6)

            return jsonify(out), 200
        except Exception as e:
            current_app.logger.exception("Unhandled error in /chat (trace_id=%s)", trace_id)
            return jsonify({"error": str(e), "trace_id": trace_id}), 500

    return chat_bp
