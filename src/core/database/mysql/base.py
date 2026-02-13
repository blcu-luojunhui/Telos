from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from quart import current_app

Base = declarative_base()

engine = None
SessionLocal: async_sessionmaker[AsyncSession] = None


def init_mysql(app):
    global engine, SessionLocal
    engine = create_async_engine(
        app.config["MYSQL_DSN"],
        pool_pre_ping=True,
        echo=False,
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def close_mysql():
    if engine:
        await engine.dispose()


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
