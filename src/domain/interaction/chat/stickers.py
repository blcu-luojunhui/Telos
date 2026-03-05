"""
表情包与情绪映射：供 small_chat 根据 agent 情绪返回对应 sticker_id。
"""

import re

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

# 回复末尾解析用：情绪表情：XXX 或 [情绪:XXX]
STICKER_TAG_PATTERN = re.compile(
    r"(?:\n|^)\s*(?:情绪表情|情绪)[:：]\s*([^\n\[\]]+?)\s*$",
    re.MULTILINE,
)
STICKER_BRACKET_PATTERN = re.compile(r"\[情绪[：:]\s*([^\]]+)\]\s*$", re.MULTILINE)


def parse_sticker_from_reply(raw: str) -> tuple[str, int | None]:
    """
    从 LLM 回复中解析出情绪标签，并去掉该部分，返回 (纯正文, sticker_id 或 None)。
    """
    if not raw or not raw.strip():
        return (raw or "", None)
    text = raw.strip()
    sticker_id = None

    # 先尝试 [情绪: XXX]
    m = STICKER_BRACKET_PATTERN.search(text)
    if m:
        emotion = m.group(1).strip()
        sticker_id = EMOTION_TO_STICKER_ID.get(emotion) or EMOTION_TO_STICKER_ID.get(
            emotion.replace(""", "").replace(""", "")
        )
        text = STICKER_BRACKET_PATTERN.sub("", text).strip()
        if sticker_id is not None:
            return (text, sticker_id)

    # 再尝试 情绪表情：XXX
    m = STICKER_TAG_PATTERN.search(text)
    if m:
        emotion = m.group(1).strip()
        sticker_id = EMOTION_TO_STICKER_ID.get(emotion) or EMOTION_TO_STICKER_ID.get(
            emotion.replace(""", "").replace(""", "")
        )
        text = STICKER_TAG_PATTERN.sub("", text).strip()
        if sticker_id is not None:
            return (text, sticker_id)

    return (text, None)
