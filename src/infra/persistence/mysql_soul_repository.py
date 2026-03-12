"""
Soul 持久化：从 souls 表读写人格列表与内容；支持种子数据（从 .md 文件初始化）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from src.infra.database.mysql import async_mysql_pool, Soul

# 与 src/soul/registry 默认人格一致，用于种子
_DEFAULT_SOULS: list[dict[str, Any]] = [
    {"slug": "rude", "name": "暴躁龙虾", "description": "有脾气、爱吐槽的赛博大龙虾，嘴硬心软", "file": "rude.md"},
    {"slug": "gentle", "name": "温柔小助手", "description": "耐心体贴，语气温和，适合需要鼓励时", "file": "gentle.md"},
    {"slug": "professional", "name": "专业简洁", "description": "简洁专业，不废话，直给结论与建议", "file": "professional.md"},
    {"slug": "funny", "name": "幽默搞怪", "description": "爱玩梗、接梗，轻松搞笑不冷场", "file": "funny.md"},
]


def _soul_dir() -> Path:
    # src/infra/persistence/ -> src/soul
    return Path(__file__).resolve().parent.parent.parent / "soul"


async def list_souls_from_db() -> list[dict[str, Any]]:
    """从 souls 表读取所有人格（id, slug, name, description）。"""
    async with async_mysql_pool.session() as session:
        stmt = (
            select(Soul)
            .where(Soul.status == "active")
            .order_by(Soul.id)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    return [
        {"id": r.id, "slug": r.slug, "name": r.name, "description": (r.description or "")}
        for r in rows
    ]


async def get_soul_content_by_id(soul_id: int) -> str:
    """按主键 id 取人格文档内容。"""
    async with async_mysql_pool.session() as session:
        stmt = select(Soul).where(Soul.id == soul_id, Soul.status == "active")
        result = await session.execute(stmt)
        row = result.scalars().first()
    if not row or not row.content:
        return ""
    return (row.content or "").strip()


async def get_soul_by_slug(slug: str) -> Optional[dict[str, Any]]:
    """按 slug 取一条人格（含 id, slug, name, description, content）。"""
    slug = (slug or "").strip().lower()
    if not slug:
        return None
    async with async_mysql_pool.session() as session:
        stmt = select(Soul).where(Soul.slug == slug, Soul.status == "active")
        result = await session.execute(stmt)
        row = result.scalars().first()
    if not row:
        return None
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "description": row.description or "",
        "content": (row.content or "").strip(),
    }


async def get_soul_id_by_slug(slug: str) -> Optional[int]:
    """按 slug 解析出 souls.id，供 chat_messages.soul_id 使用。"""
    s = await get_soul_by_slug(slug)
    return s["id"] if s else None


async def get_soul_content_async(slug: str | None) -> str:
    """
    按 slug 从 DB 取人格文档内容；若无或为空则回退到文件（registry）。
    供 small_chat 注入 system prompt。
    """
    s = await get_soul_by_slug(slug or "rude")
    if s and (s.get("content") or "").strip():
        return (s["content"] or "").strip()
    try:
        from src.soul.registry import get_soul_content as _file_content
        return _file_content(slug or "rude")
    except Exception:
        return ""


async def seed_souls_if_empty() -> int:
    """
    若 souls 表为空，则从 src/soul/*.md 种子写入默认人格；否则不修改。
    返回本次插入条数。
    """
    async with async_mysql_pool.session() as session:
        count_stmt = select(Soul).limit(1)
        r = await session.execute(count_stmt)
        if r.scalars().first() is not None:
            return 0

        soul_dir = _soul_dir()
        inserted = 0
        for item in _DEFAULT_SOULS:
            content = ""
            path = soul_dir / item["file"]
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8").strip()
                except OSError:
                    pass
            rec = Soul(
                slug=item["slug"],
                name=item["name"],
                description=item.get("description") or "",
                content=content or None,
                status="active",
            )
            session.add(rec)
            inserted += 1
        await session.commit()
    return inserted
