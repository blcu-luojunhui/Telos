"""
ReAct 智能体：Thought → Action → Observation 循环，直到 Finish 或达到最大步数。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from src.config import Config, LLMProviderType
from src.infra.external import LLMGateway
from src.infra.tools import ToolExecutor

from ._prompts import build_system_prompt, build_user_prompt


@dataclass
class ReActStep:
    """单步：思考 + 行动 + 观察（若有）。"""
    thought: str
    action: str  # 原始 Action 文本，如 "search[关键词]" 或 "Finish[答案]"
    observation: Optional[str] = None


@dataclass
class ReActResult:
    """一次 run 的结果。"""
    final_answer: Optional[str] = None  # Finish[answer] 时的 answer
    steps: list[ReActStep] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None


# 从 LLM 输出中解析 Thought 和 Action
_THOUGHT_PATTERN = re.compile(
    r"(?:Thought|思考)\s*[：:]\s*(.+?)(?=(?:Action|行动)\s*[：:]|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_ACTION_PATTERN = re.compile(
    r"(?:Action|行动)\s*[：:]\s*(.+?)(?=(?:Thought|思考)\s*[：:]|\Z)",
    re.DOTALL | re.IGNORECASE,
)
# Action 内容: `tool_name[input]` 或 `Finish[answer]`
_ACTION_CMD_PATTERN = re.compile(r"`?(\w+)\s*\[\s*([^\]]*)\s*\]`?", re.IGNORECASE)


def _parse_thought_and_action(llm_text: str) -> tuple[str, Optional[str], Optional[str]]:
    """
    解析 LLM 输出，返回 (thought, tool_name, tool_input)。
    若 Action 是 Finish[xxx]，tool_name 为 "Finish"，tool_input 为最终答案。
    """
    thought = ""
    action_raw = ""

    m_thought = _THOUGHT_PATTERN.search(llm_text)
    if m_thought:
        thought = m_thought.group(1).strip()

    m_action = _ACTION_PATTERN.search(llm_text)
    if m_action:
        action_raw = m_action.group(1).strip()

    if not action_raw:
        return thought, None, None

    m_cmd = _ACTION_CMD_PATTERN.search(action_raw)
    if not m_cmd:
        return thought, None, None

    name, inp = m_cmd.group(1).strip(), m_cmd.group(2).strip()
    return thought, name, inp


class ReActAgent:
    """
    ReAct 智能体：使用项目配置的 LLM，与 ToolExecutor 配合，
    循环执行 Thought → Action → Observation，直到 Finish 或达到 max_steps。
    """

    def __init__(
        self,
        tool_executor: ToolExecutor,
        max_steps: int = 8,
        llm_provider: Optional[LLMProviderType] = None,
        **tool_kwargs: Any,
    ):
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.llm_provider = llm_provider or Config().llm_provider
        self._tool_kwargs = tool_kwargs  # 执行工具时传入，如 user_id, reference_date

    async def run(self, question: str, **tool_kwargs: Any) -> ReActResult:
        """
        运行 ReAct 循环解答 question。
        额外 tool_kwargs 会与构造时的 _tool_kwargs 合并，传给工具执行器。
        """
        kwargs = {**self._tool_kwargs, **tool_kwargs}
        gateway = LLMGateway(provider=self.llm_provider)
        tools_desc = self.tool_executor.get_tools_description()
        system_prompt = build_system_prompt(tools_desc)

        trajectory: list[ReActStep] = []
        history_parts: list[str] = []

        for step_num in range(1, self.max_steps + 1):
            history_str = "\n\n".join(history_parts) if history_parts else ""
            user_content = build_user_prompt(question, history_str)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]

            try:
                result = await gateway.chat(messages, temperature=0.2)
                text = result.text
            except Exception as e:
                return ReActResult(
                    steps=trajectory,
                    success=False,
                    error=f"LLM 调用失败: {e!s}",
                )

            if not text:
                return ReActResult(
                    steps=trajectory,
                    success=False,
                    error="LLM 未返回有效内容",
                )

            thought, tool_name, tool_input = _parse_thought_and_action(text)

            if not tool_name:
                trajectory.append(ReActStep(thought=thought, action=text))
                history_parts.append(f"Thought: {thought}\nAction: {text}\nObservation: 格式无效，请按 工具名[输入] 或 Finish[答案] 重试。")
                continue

            if tool_name.lower() == "finish":
                trajectory.append(ReActStep(thought=thought, action=f"Finish[{tool_input}]"))
                return ReActResult(
                    final_answer=tool_input or None,
                    steps=trajectory,
                    success=True,
                )

            observation = self.tool_executor.run(tool_name, tool_input or "", **kwargs)
            step = ReActStep(thought=thought, action=f"{tool_name}[{tool_input}]", observation=observation)
            trajectory.append(step)
            history_parts.append(
                f"Thought: {thought}\nAction: {tool_name}[{tool_input}]\nObservation: {observation}"
            )

        return ReActResult(
            steps=trajectory,
            success=False,
            error=f"达到最大步数 {self.max_steps} 仍未 Finish",
        )
