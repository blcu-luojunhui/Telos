"""
领域层：业务能力。

- interaction：交互业务（NLU、记录、重复检测、对话等）
- decision：决策业务（预留，如目标与计划相关的推荐、调整等）
"""

# 各子域通过 domain.interaction、domain.decision 使用，此处不聚合导出，避免循环依赖

__all__: list[str] = []
