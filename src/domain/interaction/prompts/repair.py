"""
JSON 修复 Prompt：当 NLU 输出的 JSON 校验失败时，交给 LLM 做最小改动修复。
"""

from langchain_core.prompts import ChatPromptTemplate

REPAIR_SYSTEM_TEMPLATE = """\
你是一个 JSON 修复器。你会收到：
- 原始用户输入
- 参考日期
- 需要满足的 intent/payload 规则
- 以及 Pydantic 校验错误信息

请只做"最小改动"修复 JSON，使其：
1) 仍然与用户输入语义一致，不要编造事实
2) 满足字段名与类型要求（缺失关键字段时，若无法从文本确定，则将 intent 设为 unknown 并给 payload {{}})
3) 只输出一个 JSON 对象，不要 markdown，不要解释"""

REPAIR_HUMAN_TEMPLATE = """\
参考日期：{reference_date}
用户输入：{raw_message}
预处理提示：{hints_json}
当前 JSON：{current_json}
校验错误：{validation_error}
请输出修复后的 JSON。"""

repair_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", REPAIR_SYSTEM_TEMPLATE),
        ("human", REPAIR_HUMAN_TEMPLATE),
    ]
)
