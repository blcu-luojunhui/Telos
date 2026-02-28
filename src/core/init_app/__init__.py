import logging

from quart import Quart

from src.config import Config
from src.core.database.mysql import async_mysql_pool
from src.core.routes.v1 import register_routes

logger = logging.getLogger(__name__)


def init_quart_app():
    logger.info("Initializing Quart app")
    app = Quart(__name__)
    app.config.from_object(Config)

    logger.info("Initializing MySQL connection pool")
    async_mysql_pool.init(app)

    register_routes(app)
    logger.info("Routes registered")

    @app.before_serving
    async def startup():
        logger.info("App serving: creating database tables if not exist")
        await async_mysql_pool.create_tables()
        logger.info("Database tables ready")

    @app.after_serving
    async def shutdown():
        logger.info("App shutting down: closing MySQL connection pool")
        await async_mysql_pool.close()
        logger.info("MySQL connection pool closed")

    logger.info("Quart app initialized")
    return app


__all__ = ["init_quart_app"]
