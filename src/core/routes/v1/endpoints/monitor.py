"""
监控接口：用于在后台页面查看会话与消息详情，帮助观察 Agent 运行情况。

当前功能（MVP）：
- 按用户列出最近的会话（conversations）
- 查看指定会话下的所有消息（chat_messages）及 pending 确认状态
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quart import Blueprint, jsonify, request
from sqlalchemy import func, select, desc

from src.core.routes.auth import jwt_required
from src.infra.database.mysql import async_mysql_pool, Conversation, ChatMessage, PendingAction


def _dt_to_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.isoformat()


def create_monitor_bp() -> Blueprint:
    monitor_bp = Blueprint("monitor", __name__, url_prefix="/v1/api/monitor")

    @monitor_bp.route("/conversations", methods=["GET"])
    @jwt_required
    async def list_conversations():
        """
        列出最近的会话，用于后台监控列表。

        Query:
        - user_id: 可选，按用户过滤
        - limit:   可选，默认 50，最大 200

        返回:
        {
          "items": [
            {
              "id": 123,
              "user_id": "user_001",
              "status": "active",
              "created_at": "...",
              "updated_at": "...",
              "last_message": "最近一条消息内容",
              "last_role": "user" | "assistant",
              "last_msg_type": "saved" | "needs_confirm" | ... | null,
              "message_count": 10,
            },
            ...
          ]
        }
        """
        user_id = (request.args.get("user_id") or "").strip() or None
        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))

        async with async_mysql_pool.session() as session:
            # 先按 updated_at 倒序拿到符合条件的会话
            stmt = select(Conversation).order_by(desc(Conversation.updated_at)).limit(limit)
            if user_id:
                stmt = stmt.where(Conversation.user_id == user_id)
            conv_result = await session.execute(stmt)
            conversations = conv_result.scalars().all()

            if not conversations:
                return jsonify({"items": []}), 200

            conv_ids = [c.id for c in conversations]

            # 统计每个会话的消息数量
            count_stmt = (
                select(ChatMessage.conversation_id, func.count(ChatMessage.id))
                .where(ChatMessage.conversation_id.in_(conv_ids))
                .group_by(ChatMessage.conversation_id)
            )
            count_result = await session.execute(count_stmt)
            count_map: dict[int, int] = {row[0]: int(row[1]) for row in count_result.all()}

            # 获取每个会话的最后一条消息
            last_stmt = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id.in_(conv_ids))
                .order_by(ChatMessage.conversation_id, desc(ChatMessage.created_at), desc(ChatMessage.id))
            )
            last_result = await session.execute(last_stmt)
            last_rows = last_result.scalars().all()
            last_map: dict[int, ChatMessage] = {}
            for msg in last_rows:
                if msg.conversation_id is None:
                    continue
                if msg.conversation_id not in last_map:
                    last_map[msg.conversation_id] = msg

        items: list[dict[str, Any]] = []
        for conv in conversations:
            last_msg = last_map.get(conv.id)
            items.append(
                {
                    "id": conv.id,
                    "user_id": conv.user_id,
                    "status": conv.status,
                    "created_at": _dt_to_iso(conv.created_at),
                    "updated_at": _dt_to_iso(conv.updated_at),
                    "message_count": count_map.get(conv.id, 0),
                    "last_message": (last_msg.content if last_msg else None),
                    "last_role": (last_msg.role if last_msg else None),
                    "last_msg_type": (last_msg.msg_type if last_msg else None),
                }
            )

        return jsonify({"items": items}), 200

    @monitor_bp.route("/conversations/<int:conversation_id>", methods=["GET"])
    @jwt_required
    async def conversation_detail(conversation_id: int):
        """
        查看指定会话的详细消息列表，用于排查某次对话过程。

        返回:
        {
          "conversation": { ... },
          "messages": [
            {
              "id": 1,
              "role": "user" | "assistant" | "system",
              "content": "...",
              "msg_type": "...",
              "extra": { ... } | null,
              "created_at": "...",
            },
            ...
          ],
          "pending": {
            "id": ...,
            "created_at": "...",
            "parsed": { ... },
            "duplicate": { ... }
          } | null
        }
        """
        async with async_mysql_pool.session() as session:
            conv_stmt = select(Conversation).where(Conversation.id == conversation_id).limit(1)
            conv_res = await session.execute(conv_stmt)
            conv = conv_res.scalars().one_or_none()
            if conv is None:
                return jsonify({"error": "conversation not found"}), 404

            msg_stmt = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at, ChatMessage.id)
            )
            msg_res = await session.execute(msg_stmt)
            msgs = msg_res.scalars().all()

            pending_stmt = (
                select(PendingAction)
                .where(PendingAction.conversation_id == conversation_id)
                .order_by(desc(PendingAction.created_at))
                .limit(1)
            )
            pend_res = await session.execute(pending_stmt)
            pending = pend_res.scalars().one_or_none()

        conv_data = {
            "id": conv.id,
            "user_id": conv.user_id,
            "status": conv.status,
            "created_at": _dt_to_iso(conv.created_at),
            "updated_at": _dt_to_iso(conv.updated_at),
        }

        messages = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "msg_type": m.msg_type,
                "extra": m.extra,
                "created_at": _dt_to_iso(m.created_at),
            }
            for m in msgs
        ]

        pending_data: dict[str, Any] | None = None
        if pending is not None:
            snap = pending.snapshot_json if isinstance(pending.snapshot_json, dict) else {}
            pending_data = {
                "id": pending.id,
                "user_id": pending.user_id,
                "conversation_id": pending.conversation_id,
                "pending_type": pending.pending_type,
                "parsed": snap.get("parsed"),
                "duplicate": snap.get("duplicate"),
                "created_at": _dt_to_iso(pending.created_at),
            }

        return jsonify(
            {
                "conversation": conv_data,
                "messages": messages,
                "pending": pending_data,
            }
        ), 200

    return monitor_bp

