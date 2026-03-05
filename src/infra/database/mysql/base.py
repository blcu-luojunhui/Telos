"""
MySQL 仅通过 SQLAlchemy 异步 engine + Session 访问，与 models 配套。
驱动：aiomysql（mysql+aiomysql://），配置来自 BetterMeMySQLConfig。
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AsyncMySQL:
    """
    异步 MySQL 连接封装，持有 engine 与 session 工厂。
    使用前需调用 init(app) 或 init(dsn=...)，使用完毕后可调用 close()。
    """

    __slots__ = ("_engine", "_session_factory")

    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    @property
    def engine(self) -> Optional[AsyncEngine]:
        return self._engine

    def init(self, app: Any = None, *, dsn: Optional[str] = None) -> None:
        """
        初始化 SQLAlchemy 异步 engine 与 Session。
        - 传入 app：优先用 app.config["MYSQL_DSN"]，否则用 Config().mysql_config
        - 传入 dsn：直接使用该 DSN（测试或非 Quart 场景）
        """
        url: Optional[str] = None
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

        echo = bool(app and app.config.get("DEBUG")) if app else False
        self._engine = create_async_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            echo=echo,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def create_tables(self) -> None:
        """
        根据 ORM 模型创建所有表（若不存在）。
        需在 init() 之后调用；会确保 models 已导入（通过 mysql/__init__.py）。
        """
        if self._engine is None:
            return
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """释放连接池，之后需重新 init 才能使用。"""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取异步 Session 的上下文管理器。
        未初始化时抛出 RuntimeError。
        """
        if self._session_factory is None:
            raise RuntimeError("init() must be called before using database sessions")
        async with self._session_factory() as session:
            yield session

    async def get_db(self) -> AsyncGenerator[AsyncSession, None]:
        """依赖注入用：yield 一个 Session，供 FastAPI/Quart 等 get_db 使用。"""
        async with self.session() as session:
            yield session
