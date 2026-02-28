from src.core.routes.v1.endpoints import create_record_bp
from src.core.routes.v1.endpoints import create_health_bp
from src.core.routes.v1.websocket import ws_bp


def register_routes(app):
    app.register_blueprint(create_record_bp())
    app.register_blueprint(create_health_bp())
    app.register_blueprint(ws_bp)


__ALL__ = ["register_routes"]
