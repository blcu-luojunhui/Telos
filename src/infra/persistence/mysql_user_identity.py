"""
V2 用户标识映射：
- 对上层继续使用 user_code (str)
- 对数据库使用 users.id (bigint)
"""

from __future__ import annotations

from sqlalchemy import select

from src.infra.database.mysql import async_mysql_pool, User


async def get_or_create_user_id(user_code: str) -> int:
    code = (user_code or "").strip()
    if not code:
        raise ValueError("user_code is required")

    async with async_mysql_pool.session() as session:
        row = await session.execute(select(User).where(User.user_code == code).limit(1))
        user = row.scalars().first()
        if user is not None:
            return int(user.id)
        user = User(user_code=code, status="active")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return int(user.id)

