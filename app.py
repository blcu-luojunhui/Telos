from quart import Quart
from src.config import Config
from src.core.routes import register_routes


def create_app():
    app = Quart(__name__)
    app.config.from_object(Config)

    # 注册路由
    register_routes(app)

    # 服务启动前（初始化数据库 / 连接池）
    # @app.before_serving
    # async def startup():
    #     init_db(app)

    # # 服务关闭后（释放资源）
    # @app.after_serving
    # async def shutdown():
    #     await close_db()

    return app


app = create_app()

if __name__ == "__main__":
    app.run()
