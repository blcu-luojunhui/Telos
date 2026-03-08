"""
自然语言 → 意图 + 结构化 payload。

通过 LLM 将用户输入解析为 ParsedRecord，便于后续落表。
支持配置不同供应商：deepseek（默认）、openai（均使用 OpenAI 兼容 API）。
"""

from datetime import date
import json
from typing import Any, List, Optional, Sequence

from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.config import Config, LLMProviderType
from src.infra.external import LLMGateway
from src.domain.interaction.nlu.preprocess import preprocess_message
from src.domain.interaction.nlu.normalize_validate import (
    normalize_date,
    normalize_intent,
    normalize_payload,
    validate_payload,
)


SYSTEM_PROMPT = """
你是一个个人成长与生活记录助手。用户会输入一句简短的中文或英文，描述他「做了什么」「吃了什么」「身体数据」「目标」或「当前状态/心情」。
请从用户输入中识别意图，并抽取结构化信息，输出为 JSON。

顶层输出格式（有且仅有一个 JSON 对象，不要 markdown、不要多余说明）：
- 若用户一句话只表达一个意图：{"intent": "<见下>", "date": "YYYY-MM-DD 或 null", "payload": { ... }}
- 若用户一句话同时表达多个意图（例如既设定目标又要求制定计划）：输出 "intents" 数组，每项为 {"intent": "...", "date": null 或 "YYYY-MM-DD", "payload": { ... }}。例如：{"intents": [{"intent": "set_goal", "date": null, "payload": {...}}, {"intent": "request_plan", "date": null, "payload": {}}]}

若用户未提到日期，date 填 null（调用方会用当天）。payload 只包含从用户话里能推断出的字段，不要编造；主观体验类数字均为 1-10。

---

意图（intent）与对应 payload 结构如下。

1) record_workout — 运动/训练
   payload 字段（均为可选，只填能从用户话里推断出的）：
   - type: string，必填。取值为 run | basketball | strength | other
   - duration_min: number，时长（分钟）
   - distance_km: number，距离（公里）
   - avg_pace: number，配速（分钟/公里）
   - avg_hr: number，平均心率
   - calories: number，消耗卡路里
   - subjective_fatigue: number，主观疲劳 1-10
   - sleep_quality: number，睡眠质量 1-10
   - mood: number，心情 1-10
   - motivation: number，动力 1-10
   - stress_level: number，压力 1-10
   - note: string，备注

2) record_meal — 饮食
   payload 字段：
   - meal_type: string，必填。取值为 breakfast | lunch | dinner | snack
   - food_items: string，必填。吃了什么（自由文本）
   - estimated_calories: number，预估热量
   - protein_g: number，蛋白质（克）
   - carb_g: number，碳水（克）
   - fat_g: number，脂肪（克）
   - satiety: number，饱腹感 1-10
   - mood: number，心情 1-10
   - stress_level: number，压力 1-10
   - note: string，备注

3) record_body_metric — 身体指标
   payload 字段（均为可选）：
   - weight: number，体重（kg）
   - body_fat: number，体脂（%）
   - muscle_mass: number，肌肉量（kg）
   - resting_hr: number，静息心率
   - bp_systolic: number，收缩压
   - bp_diastolic: number，舒张压
   - sleep_hours: number，睡眠时长（小时）
   - note: string，备注

4) set_goal — 设定目标
   payload 字段：
   - type: string，必填。取值为 weight_loss | muscle_gain | maintenance | race 等
   - target: object，可选。按 type 不同：
     - weight_loss: 如 { "start_weight": 70, "target_weight": 65 }
     - muscle_gain: 如 { "target_weight": 75 }
     - race: { "race_type": "half_marathon"|"10k"|"full_marathon" 等, "race_date": "YYYY-MM-DD", "target_time": "2:00:00", "weekly_time_budget": 300 }
   - deadline: string，可选，格式 "YYYY-MM-DD"
   - note: string，备注

5) record_status — 当日整体状态/心情
   payload 字段（均为可选）：
   - mood: number，心情 1-10
   - energy: number，精力/疲劳 1-10
   - stress_level: number，压力 1-10
   - note: string，自由描述（如「今天很累」「心情一般」）

6) query_workout — 查运动记录（如「上周跑了多少」「最近跑步记录」）
   payload: date_range: string 取值为 today | yesterday | last_7_days | last_30_days；可选 workout_type: run | basketball | strength | other

7) query_meal — 查饮食记录（如「今天吃了啥」「最近饮食」）
   payload: date_range 同上；可选 meal_type: breakfast | lunch | dinner | snack

8) query_body_metric — 查身体指标（如「最近体重」「睡眠情况」）
   payload: date_range 同上

9) query_summary — 查汇总/今日概览（如「今天记了什么」「本周总结」）
   payload: date_range 同上，默认 today

10) edit_last — 修改上一条记录（如「把刚才那条距离改成6公里」「改成午餐」）
    payload: record_type 可选 workout | meal | body_metric；updates: 要改的字段，如 {"distance_km": 6} 或 {"meal_type": "lunch"}

11) delete_record — 删除某条记录（如「删掉刚才那条」「删除今天的午餐记录」）
    payload: record_type 必填 workout | meal | body_metric | goal；可选 record_id；或 date + meal_type / workout_type 定位

12) request_plan — 要求制定或查看训练计划（如「帮我制定计划」「我的计划呢」「给我看看训练安排」）。常与 set_goal 同时出现（如「我要减肥从160到150，帮我制定计划」）。
    payload: 可为 {}；可选 goal_id（若用户指定了某个目标）

13) unknown — 无法识别或与记录无关
    payload 可为 {} 或省略。
"""

# few-shot：提升稳定性（行业常用做法）
FEW_SHOT_EXAMPLES = """
示例（仅用于学习格式与字段，不要照抄具体数值）：

输入：今天中午吃了牛肉面，挺饱的
输出：{"intent":"record_meal","date":null,"payload":{"meal_type":"lunch","food_items":"牛肉面","satiety":8}}

输入：昨晚跑了 5k，30分钟，配速 6 分/公里
输出：{"intent":"record_workout","date":null,"payload":{"type":"run","distance_km":5,"duration_min":30,"avg_pace":6}}

输入：体重 140斤，昨晚睡了7小时
输出：{"intent":"record_body_metric","date":null,"payload":{"weight":70,"sleep_hours":7}}

输入：今天力量训练 45 分钟，心情一般，压力有点大
输出：{"intent":"record_workout","date":null,"payload":{"type":"strength","duration_min":45,"mood":5,"stress_level":7}}

输入：给自己定个目标：半马 2026-05-01 跑进 2 小时
输出：{"intent":"set_goal","date":null,"payload":{"type":"race","target":{"race_type":"half_marathon","race_date":"2026-05-01","target_time":"2:00:00"}}}

输入：我需要减肥，从160斤减到150斤，帮我制定一个计划
输出：{"intents":[{"intent":"set_goal","date":null,"payload":{"type":"weight_loss","target":{"start_weight":80,"target_weight":75}}},{"intent":"request_plan","date":null,"payload":{}}]}

输入：今天很累，精力 3 分
输出：{"intent":"record_status","date":null,"payload":{"energy":3,"note":"今天很累"}}

输入：我上周跑了多少
输出：{"intent":"query_workout","date":null,"payload":{"date_range":"last_7_days"}}

输入：今天午饭吃了啥
输出：{"intent":"query_meal","date":null,"payload":{"date_range":"today","meal_type":"lunch"}}

输入：最近体重趋势
输出：{"intent":"query_body_metric","date":null,"payload":{"date_range":"last_30_days"}}

输入：把刚才那条距离改成 6 公里
输出：{"intent":"edit_last","date":null,"payload":{"record_type":"workout","updates":{"distance_km":6}}}

输入：删掉今天的午餐记录
输出：{"intent":"delete_record","date":null,"payload":{"record_type":"meal","date":"YYYY-MM-DD","meal_type":"lunch"}}
""".strip()


REPAIR_SYSTEM_PROMPT = """
你是一个 JSON 修复器。你会收到：
- 原始用户输入
- 参考日期
- 需要满足的 intent/payload 规则
- 以及 Pydantic 校验错误信息

请只做“最小改动”修复 JSON，使其：
1) 仍然与用户输入语义一致，不要编造事实
2) 满足字段名与类型要求（缺失关键字段时，若无法从文本确定，则将 intent 设为 unknown 并给 payload {}）
3) 只输出一个 JSON 对象，不要 markdown，不要解释
""".strip()


def _extract_json(text: str) -> dict:
    """
    尽量从 LLM 输出里提取 JSON object。
    """
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        t = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        # 兜底：截取第一个 {...} 区间
        i = t.find("{")
        j = t.rfind("}")
        if i >= 0 and j > i:
            return json.loads(t[i : j + 1])
        return {}


def _parse_one(
    data: dict,
    ref: date,
    pre: Any,
    message: str,
) -> ParsedRecord:
    """解析单条 intent 为 ParsedRecord（用于单条或 intents 数组中的一项）。"""
    intent = normalize_intent(data.get("intent"))
    parsed_date = normalize_date(data.get("date"), ref, hints=pre.hints)
    payload = normalize_payload(intent, data.get("payload"), hints=pre.hints)
    payload, err = validate_payload(intent, payload)
    if err and intent != IntentType.UNKNOWN:
        intent = IntentType.UNKNOWN
        payload = {}
    return ParsedRecord(
        intent=intent,
        date=parsed_date,
        payload=payload,
        raw_message=message.strip(),
    )


async def parse_user_message(
    message: str,
    reference_date: Optional[date] = None,
    history: Optional[Sequence[dict]] = None,
) -> List[ParsedRecord]:
    """
    将用户自然语言解析为结构化记录，支持一句话多意图。

    :param message: 用户输入，如「今天中午吃了牛肉面」「我要减肥从160到150，帮我制定计划」
    :param reference_date: 若用户未说日期，用此日期（默认今天）
    :return: List[ParsedRecord]，通常一条；若用户同时表达多个意图（如目标+计划）则多条
    """
    ref = reference_date or date.today()
    ref_str = ref.isoformat()

    # Stage 0：预处理（日期/餐次/运动类型/单位归一提示）
    pre = preprocess_message(message, ref)

    # 构建对话历史（用于让模型理解上下文，如「和刚才一样」「帮我再记一条」）
    history_lines: list[str] = []
    if history:
        for turn in history:
            role = str(turn.get("role") or "").strip() or "user"
            content = str(turn.get("content") or "").strip()
            if not content:
                continue
            # 限制每条历史长度，避免 prompt 过长
            if len(content) > 200:
                content = content[:200] + "…"
            history_lines.append(f"{role}: {content}")

    history_block = ""
    if history_lines:
        history_block = (
            "对话历史（从旧到新，最多最近若干条）：\n"
            + "\n".join(history_lines)
            + "\n\n"
        )

    provider: LLMProviderType = Config().llm_provider
    gateway = LLMGateway(provider=provider)

    user_content = (
        f"参考日期（若用户未说日期则用此日）：{ref_str}\n"
        f"预处理提示（高置信线索）：{json.dumps(pre.hints, ensure_ascii=False)}\n\n"
        f"{history_block}"
        f"当前轮用户输入（原文）：{message.strip()}\n"
        f"当前轮用户输入（轻量归一）：{pre.normalized_text}"
    )

    result = await gateway.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLES},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
    )
    text = result.text or "{}"
    data = _extract_json(text)

    # 多意图：直接解析 intents 数组，不做 repair
    intents_raw = data.get("intents")
    if isinstance(intents_raw, list) and len(intents_raw) > 0:
        out: List[ParsedRecord] = []
        for item in intents_raw:
            if isinstance(item, dict):
                out.append(_parse_one(item, ref, pre, message))
        if out:
            return out
        # 若数组项都无效，退回到单意图
    # 单意图：原有逻辑（含 repair）
    intent = normalize_intent(data.get("intent"))
    parsed_date = normalize_date(data.get("date"), ref, hints=pre.hints)
    payload = normalize_payload(intent, data.get("payload"), hints=pre.hints)
    payload, err = validate_payload(intent, payload)

    if err:
        repair_user = (
            f"参考日期：{ref_str}\n"
            f"用户输入：{message.strip()}\n"
            f"预处理提示：{json.dumps(pre.hints, ensure_ascii=False)}\n"
            f"当前 JSON：{json.dumps({'intent': intent.value, 'date': parsed_date.isoformat(), 'payload': payload}, ensure_ascii=False)}\n"
            f"校验错误：{err}\n"
            f"请输出修复后的 JSON。"
        )
        repair_result = await gateway.chat(
            [
                {
                    "role": "system",
                    "content": REPAIR_SYSTEM_PROMPT + "\n\n" + SYSTEM_PROMPT,
                },
                {"role": "user", "content": repair_user},
            ],
            temperature=0.0,
        )
        repair_text = repair_result.text or "{}"
        repair_data = _extract_json(repair_text)
        intent = normalize_intent(repair_data.get("intent"))
        parsed_date = normalize_date(repair_data.get("date"), ref, hints=pre.hints)
        payload = normalize_payload(intent, repair_data.get("payload"), hints=pre.hints)
        payload, err2 = validate_payload(intent, payload)
        if err2 and intent != IntentType.UNKNOWN:
            intent = IntentType.UNKNOWN
            payload = {}

    return [
        ParsedRecord(
            intent=intent,
            date=parsed_date,
            payload=payload,
            raw_message=message.strip(),
        )
    ]
