"""
自然语言 → 意图 + 结构化 payload。

通过 LLM 将用户输入解析为 ParsedRecord，便于后续落表。
支持配置不同供应商：deepseek（默认）、openai（均使用 OpenAI 兼容 API）。
"""

from datetime import date
import json
from typing import Optional

from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.config import Config, LLMProviderType


SYSTEM_PROMPT = """你是一个个人成长与生活记录助手。用户会输入一句简短的中文或英文，描述他「做了什么」「吃了什么」「身体数据」「目标」或「当前状态/心情」。
请从用户输入中识别意图，并抽取结构化信息，输出为 JSON。

意图类型（intent）只能取以下之一：
- record_workout: 运动/训练（跑步、打球、力量等）
- record_meal: 饮食（早/中/晚/加餐吃了什么）
- record_body_metric: 身体指标（体重、体脂、睡眠时长等）
- set_goal: 设定目标（减脂、半马、维持等）
- record_status: 当日整体状态/心情/感受（如「今天很累」「心情一般」）
- unknown: 无法识别或与记录无关

规则：
1. 若未提到日期，date 填 null（调用方会用当天）。
2. payload 只包含从用户话里能推断出的字段，不要编造；数字类主观体验为 1-10。
3. 训练类型：run / basketball / strength / other。饮食类型：breakfast / lunch / dinner / snack。
4. 目标 type：weight_loss / muscle_gain / maintenance / race 等；race 时 target 可含 race_type(half_marathon/10k/full_marathon等)、race_date、target_time、weekly_time_budget。
5. 只输出一个 JSON 对象，不要 markdown 包裹，不要多余说明。

输出格式（JSON）：
{"intent": "<上述之一>", "date": "YYYY-MM-DD 或 null", "payload": { ... }}"""


def _get_llm_client_and_model(provider: LLMProviderType):
    """
    根据当前配置返回 (AsyncOpenAI client, model_name)。
    DeepSeek 与 OpenAI 均使用 OpenAI 兼容接口，通过 base_url 区分。
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("请安装 openai: pip install openai（DeepSeek 也使用该客户端）")

    cfg = Config()
    if provider == "deepseek":
        d = cfg.deepseek
        if not d.api_key:
            raise ValueError("DeepSeek API Key 未配置（DEEP_SEEK_API_KEY）")
        client = AsyncOpenAI(api_key=d.api_key, base_url=d.base_url)
        return client, d.model
    if provider == "openai":
        o = cfg.openai
        if not o.api_key:
            raise ValueError("OpenAI API Key 未配置（OPENAI_API_KEY）")
        client = AsyncOpenAI(api_key=o.api_key)
        return client, o.model
    raise ValueError(f"不支持的 LLM 供应商: {provider}，可选: deepseek | openai")


async def parse_user_message(
    message: str,
    reference_date: Optional[date] = None,
) -> ParsedRecord:
    """
    将用户自然语言解析为结构化记录。

    :param message: 用户输入，如「今天中午吃了牛肉面，挺饱的」「下午跑了 5 公里」
    :param reference_date: 若用户未说日期，用此日期（默认今天）
    :return: ParsedRecord，含 intent、date、payload、raw_message
    """
    ref = reference_date or date.today()
    ref_str = ref.isoformat()

    provider: LLMProviderType = Config().llm_provider
    client, model = _get_llm_client_and_model(provider)

    user_content = (
        f"参考日期（若用户未说日期则用此日）：{ref_str}\n\n用户输入：{message.strip()}"
    )

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
    )
    text = response.choices[0].message.content or "{}"
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    data = json.loads(text)

    intent_str = (data.get("intent") or "unknown").strip().lower()
    try:
        intent = IntentType(intent_str)
    except ValueError:
        intent = IntentType.UNKNOWN

    raw_date = data.get("date")
    parsed_date = None
    if raw_date:
        if isinstance(raw_date, str) and raw_date.lower() != "null":
            try:
                parsed_date = date.fromisoformat(raw_date[:10])
            except (ValueError, TypeError):
                pass
        if parsed_date is None and isinstance(raw_date, date):
            parsed_date = raw_date
    if parsed_date is None:
        parsed_date = ref

    return ParsedRecord(
        intent=intent,
        date=parsed_date,
        payload=data.get("payload"),
        raw_message=message.strip(),
    )
