"""
BetterMe 应用入口。
"""

import logging

from quart import Quart

from src.config import Config
from src.infra.database.mysql import async_mysql_pool
from src.core.routes.v1 import register_routes
from src.infra.shared import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def create_app() -> Quart:
    _app = Quart(__name__)
    _app.config.from_object(Config)

    @_app.before_serving
    async def startup():
        logger.info("Initializing async MySQL pool")
        async_mysql_pool.init(_app)
        logger.info("Creating database tables if not exist")
        await async_mysql_pool.create_tables()
        logger.info("Wiring chat application service")
        from src.core.service import create_chat_application_service
        _app.chat_service = create_chat_application_service()
        logger.info("Registering routes")
        register_routes(_app)
        logger.info("MySQL ready")

    @_app.after_serving
    async def shutdown():
        logger.info("Closing MySQL connection pool")
        await async_mysql_pool.close()
        logger.info("Shutdown complete")

    logger.info("App created")
    return _app


app = create_app()

if __name__ == "__main__":
    app.run()
