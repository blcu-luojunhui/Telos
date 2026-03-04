# ReAct 提示词：系统说明 + 格式要求 + 少样本
from __future__ import annotations

REACT_SYSTEM = """你是一个能调用外部工具的智能助手（ReAct 风格）。你需要交替进行「思考」和「行动」：
- 思考：分析问题、拆解任务、规划下一步、根据观察总结。
- 行动：只能从可用工具中选一个调用，或给出最终答案。

你必须严格按下面格式回复，每次只输出一对 Thought 和 Action。

格式（每轮只出现一次）：
Thought: 你的推理过程（一句话或简短多句）
Action: 以下两种之一：
  - 调用工具：`工具名[输入内容]`，例如 `search[关键词]`、`record_meal[午餐 牛肉面]`
  - 结束任务：`Finish[给用户的最终回答]`（当已有足够信息可直接回答用户时使用）

可用工具列表：
{tools}

注意：
- 工具名和输入都要在方括号内，不要有多余括号或换行。
- 若需要多步，先调用工具，根据 Observation 再思考、再行动，直到能 Finish。
- 不要编造工具名，只能使用上面列出的工具。"""

REACT_USER_TEMPLATE = """当前问题：
Question: {question}

{history_section}

请输出本轮的 Thought 和 Action（仅此一对）。"""

# 少样本示例（可选，用于提升格式稳定性）
REACT_FEW_SHOT = """
示例（格式参考，不要照抄内容）：
Question: 今天中午吃了什么？
Thought: 用户问的是午餐内容，需要先查询今日饮食记录。
Action: `get_meal_today[午餐]`

Observation: 今日午餐：牛肉面、凉拌黄瓜。
Thought: 已有记录，可以直接回答用户。
Action: `Finish[今天中午吃的是牛肉面、凉拌黄瓜。]`
"""


def build_system_prompt(tools_desc: str, with_few_shot: bool = True) -> str:
    base = REACT_SYSTEM.format(tools=tools_desc)
    if with_few_shot:
        base += REACT_FEW_SHOT
    return base


def build_user_prompt(question: str, history: str) -> str:
    history_section = (
        f"已有轨迹（Thought / Action / Observation）：\n{history}"
        if history.strip()
        else "（尚无轨迹，请从第一步开始。）"
    )
    return REACT_USER_TEMPLATE.format(
        question=question, history_section=history_section
    )
