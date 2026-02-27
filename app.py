from quart import Quart
from src.config import Config
from src.core.routes import register_routes
from src.core.database.mysql import init_mysql, close_mysql, create_tables


def create_app():
    app = Quart(__name__)
    app.config.from_object(Config)

    # 注册路由
    register_routes(app)

    # 服务启动时初始化 MySQL（交互层落表依赖）
    @app.before_serving
    async def startup():
        init_mysql(app)
        await create_tables()

    @app.after_serving
    async def shutdown():
        await close_mysql()

    return app


app = create_app()

if __name__ == "__main__":
    app.run()
