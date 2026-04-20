"""
表情包与情绪映射：供 small_chat 根据 agent 情绪返回对应 sticker_id。

支持两种模式：
1. 精确匹配：直接写表情名（向后兼容）
2. 类别+强度：写情绪类别和强度等级，自动选择合适的表情
"""

import re
import random

# 25 个表情名称（与前端 STICKER_FILES 顺序一致）→ sticker_id 1~25
EMOTION_TO_STICKER_ID = {
    "叉腰": 1,
    "僵住": 2,
    "发抖": 3,
    "慢慢放下": 4,
    "立正": 5,
    "翻白眼": 6,
    "气得转圈": 7,
    "钳子敲自己脑袋": 8,
    "突然瘫倒装死": 9,
    "最后弹起来比个耶": 10,
    "原地蹦迪": 11,
    "用钳子打节拍": 12,
    "突然定格耍帅": 13,
    "假装擦汗": 14,
    "最后给你抛个媚眼": 15,
    "抱头蹲防": 16,
    "偷偷瞄你": 17,
    "突然亮出加钱牌子": 18,
    '突然亮出"加钱"牌子': 18,
    "原地后空翻失败": 19,
    "躺平摆烂": 20,
    "用钳子比心": 21,
    "突然害羞捂脸": 22,
    "原地蒸发": 23,
    "从屏幕外爬回来": 24,
    "最后关机黑屏": 25,
    "加钱": 18,
    "后空翻失败": 19,
    "关机黑屏": 25,
    "比个耶": 10,
    "抛媚眼": 15,
    "捂脸": 22,
    "爬回来": 24,
    "比心": 21,
    "擦汗": 14,
    "耍帅": 13,
    "敲脑袋": 8,
    "瘫倒": 9,
    "蹦迪": 11,
    "打节拍": 12,
    "蹲防": 16,
    "瞄你": 17,
    "蒸发": 23,
}

# 情绪类别 → 按强度排列的 sticker_id 列表（低→高）
EMOTION_CATEGORIES: dict[str, list[int]] = {
    "开心": [12, 13, 10, 11, 21],       # 打节拍 → 耍帅 → 比个耶 → 蹦迪 → 比心
    "害羞": [17, 22, 15],               # 偷偷瞄你 → 害羞捂脸 → 抛媚眼
    "生气": [6, 1, 7],                  # 翻白眼 → 叉腰 → 气得转圈
    "疲惫": [14, 9, 20, 25],            # 擦汗 → 瘫倒 → 躺平摆烂 → 关机黑屏
    "害怕": [2, 3, 16, 23],             # 僵住 → 发抖 → 蹲防 → 蒸发
    "调皮": [8, 18, 19, 24],            # 敲脑袋 → 加钱牌子 → 后空翻失败 → 爬回来
    "平静": [5, 4],                     # 立正 → 慢慢放下
}

# 类别别名映射
_CATEGORY_ALIASES: dict[str, str] = {
    "高兴": "开心", "快乐": "开心", "开心": "开心", "happy": "开心",
    "害羞": "害羞", "羞涩": "害羞", "shy": "害羞",
    "生气": "生气", "愤怒": "生气", "恼火": "生气", "angry": "生气",
    "疲惫": "疲惫", "累": "疲惫", "困": "疲惫", "tired": "疲惫",
    "害怕": "害怕", "恐惧": "害怕", "慌": "害怕", "scared": "害怕",
    "调皮": "调皮", "搞怪": "调皮", "playful": "调皮",
    "平静": "平静", "淡定": "平静", "calm": "平静",
}

# 强度映射
_INTENSITY_MAP: dict[str, float] = {
    "高": 0.8, "中": 0.5, "低": 0.2,
    "强": 0.8, "弱": 0.2,
}


def select_sticker_by_emotion(emotion_text: str, intensity: float = 0.5) -> int | None:
    """
    根据情绪类别和强度选择表情。

    :param emotion_text: 情绪类别关键词（如"开心"、"生气"）
    :param intensity: 强度 0.0-1.0
    :return: sticker_id 或 None
    """
    # 先尝试精确匹配
    sid = EMOTION_TO_STICKER_ID.get(emotion_text)
    if sid is not None:
        return sid

    # 尝试类别匹配
    category = _CATEGORY_ALIASES.get(emotion_text)
    if not category:
        # 模糊匹配：检查 emotion_text 是否包含某个类别关键词
        for alias, cat in _CATEGORY_ALIASES.items():
            if alias in emotion_text:
                category = cat
                break

    if not category or category not in EMOTION_CATEGORIES:
        return None

    stickers = EMOTION_CATEGORIES[category]
    if not stickers:
        return None

    # 根据强度选择：intensity 越高，选列表越靠后的（更强烈的）
    idx = min(int(intensity * len(stickers)), len(stickers) - 1)
    return stickers[idx]


# 回复末尾解析用：情绪表情：XXX 或 [情绪:XXX]
STICKER_TAG_PATTERN = re.compile(
    r"(?:\n|^)\s*(?:情绪表情|情绪)[:：]\s*([^\n\[\]]+?)\s*$",
    re.MULTILINE,
)
STICKER_BRACKET_PATTERN = re.compile(r"\[情绪[：:]\s*([^\]]+)\]\s*$", re.MULTILINE)

# 新格式：情绪表情：开心（强度：高）
STICKER_CATEGORY_PATTERN = re.compile(
    r"(?:\n|^)\s*(?:情绪表情|情绪)[:：]\s*(\S+?)(?:[（(]强度[:：]\s*(\S+?)[）)])?\s*$",
    re.MULTILINE,
)


def parse_sticker_from_reply(raw: str) -> tuple[str, int | None]:
    """
    从 LLM 回复中解析出情绪标签，并去掉该部分，返回 (纯正文, sticker_id 或 None)。

    支持三种格式：
    1. 情绪表情：开心（强度：高）  → 类别+强度
    2. 情绪表情：翻白眼            → 精确匹配
    3. [情绪: XXX]                 → 精确匹配
    """
    if not raw or not raw.strip():
        return (raw or "", None)
    text = raw.strip()
    sticker_id = None

    # 先尝试新格式：类别+强度
    m = STICKER_CATEGORY_PATTERN.search(text)
    if m:
        emotion = m.group(1).strip()
        intensity_text = (m.group(2) or "中").strip()
        intensity = _INTENSITY_MAP.get(intensity_text, 0.5)

        # 先尝试精确匹配
        sticker_id = EMOTION_TO_STICKER_ID.get(emotion) or EMOTION_TO_STICKER_ID.get(
            emotion.replace("\u201c", "").replace("\u201d", "")
        )
        # 再尝试类别匹配
        if sticker_id is None:
            sticker_id = select_sticker_by_emotion(emotion, intensity)

        if sticker_id is not None:
            text = STICKER_CATEGORY_PATTERN.sub("", text).strip()
            return (text, sticker_id)

    # 尝试 [情绪: XXX]
    m = STICKER_BRACKET_PATTERN.search(text)
    if m:
        emotion = m.group(1).strip()
        sticker_id = EMOTION_TO_STICKER_ID.get(emotion) or EMOTION_TO_STICKER_ID.get(
            emotion.replace("\u201c", "").replace("\u201d", "")
        )
        if sticker_id is None:
            sticker_id = select_sticker_by_emotion(emotion)
        text = STICKER_BRACKET_PATTERN.sub("", text).strip()
        if sticker_id is not None:
            return (text, sticker_id)

    # 尝试 情绪表情：XXX（旧格式兜底）
    m = STICKER_TAG_PATTERN.search(text)
    if m:
        emotion = m.group(1).strip()
        sticker_id = EMOTION_TO_STICKER_ID.get(emotion) or EMOTION_TO_STICKER_ID.get(
            emotion.replace("\u201c", "").replace("\u201d", "")
        )
        if sticker_id is None:
            sticker_id = select_sticker_by_emotion(emotion)
        text = STICKER_TAG_PATTERN.sub("", text).strip()
        if sticker_id is not None:
            return (text, sticker_id)

    return (text, None)
