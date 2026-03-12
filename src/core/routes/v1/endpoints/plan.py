"""
训练计划接口：生成计划预览（不落库）、用户确认后落库。
"""

from datetime import date

from quart import Blueprint, request, jsonify
from sqlalchemy import select

from src.infra.database.mysql import async_mysql_pool, Goal
from src.domain.interaction.record.training_plan import build_plan_preview, save_plan


def create_plan_bp() -> Blueprint:
    plan_bp = Blueprint("plan", __name__, url_prefix="/v1/api")

    @plan_bp.route("/plan/preview", methods=["POST"])
    async def plan_preview():
        """
        根据目标生成计划预览（不写库），供前端表格展示。
        Body: { "user_id": "...", "goal_id": 123 }
        """
        data = await request.get_json() or {}
        user_id = (data.get("user_id") or "").strip()
        goal_id = data.get("goal_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        if goal_id is None:
            return jsonify({"error": "goal_id is required"}), 400
        try:
            goal_id = int(goal_id)
        except (TypeError, ValueError):
            return jsonify({"error": "goal_id must be an integer"}), 400

        async with async_mysql_pool.session() as session:
            result = await session.execute(
                select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
            )
            goal = result.scalars().first()
        if not goal:
            return jsonify({"error": "goal not found or not owned by user"}), 404

        preview = build_plan_preview(goal)
        if not preview:
            return jsonify({"error": "unsupported goal type for plan"}), 400

        return jsonify(preview), 200

    @plan_bp.route("/plan/confirm", methods=["POST"])
    async def plan_confirm():
        """
        用户确认计划后落库。
        Body: { "user_id": "...", "goal_id": 123, "plan": { ... } }
        plan 为预览接口返回的完整结构（含 title, start_date, end_date, days[].sessions[]）。
        """
        data = await request.get_json() or {}
        user_id = (data.get("user_id") or "").strip()
        goal_id = data.get("goal_id")
        plan_payload = data.get("plan")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        if goal_id is None:
            return jsonify({"error": "goal_id is required"}), 400
        if not plan_payload or not isinstance(plan_payload, dict):
            return jsonify({"error": "plan is required and must be an object"}), 400
        try:
            goal_id = int(goal_id)
        except (TypeError, ValueError):
            return jsonify({"error": "goal_id must be an integer"}), 400

        async with async_mysql_pool.session() as session:
            result = await session.execute(
                select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
            )
            goal = result.scalars().first()
            if not goal:
                return jsonify({"error": "goal not found or not owned by user"}), 404

            try:
                tp, sessions_count = await save_plan(session, user_id, goal_id, plan_payload)
                await session.commit()
            except Exception as e:
                await session.rollback()
                return jsonify({"error": str(e)}), 500

        return (
            jsonify(
                {
                    "ok": True,
                    "training_plan_id": tp.id,
                    "goal_id": goal_id,
                    "sessions_count": sessions_count,
                    "message": f"计划已保存，共 {sessions_count} 次训练，训练日前一天会提醒你。",
                }
            ),
            200,
        )

    return plan_bp
