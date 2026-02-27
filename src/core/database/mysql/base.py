"""
MySQL 仅通过 SQLAlchemy 异步 engine + Session 访问，与 models 配套。
驱动：aiomysql（mysql+aiomysql://），配置来自 BetterMeMySQLConfig。
"""
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

engine = None
SessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def init_mysql(app=None, *, dsn: Optional[str] = None):
    """
    初始化 SQLAlchemy 异步 engine 与 Session。
    - 传入 app：优先用 app.config["MYSQL_DSN"]，否则用 Config().mysql_config
    - 传入 dsn：直接使用该 DSN（测试或非 Quart 场景）
    """
    global engine, SessionLocal
    url = None
    if app:
        url = app.config.get("MYSQL_DSN")
    if not url and dsn:
        url = dsn
    if not url:
        from src.config import Config
        cfg = Config().better_me
        url = cfg.async_sqlalchemy_url()
        pool_size = getattr(cfg, "minsize", 5)
        max_overflow = max(0, getattr(cfg, "maxsize", 20) - pool_size)
    else:
        pool_size, max_overflow = 5, 15
    engine = create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        echo=bool(app and app.config.get("DEBUG")),
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_tables():
    """
    根据 ORM 模型创建所有表（若不存在）。
    需在 init_mysql() 之后调用；会确保 models 已导入（通过 mysql/__init__.py）。
    """
    global engine
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_mysql():
    global engine, SessionLocal
    if engine:
        await engine.dispose()
        engine = None
        SessionLocal = None


async def get_db() -> AsyncSession:
    if SessionLocal is None:
        raise RuntimeError("init_mysql() must be called before get_db()")
    async with SessionLocal() as session:
        yield session
