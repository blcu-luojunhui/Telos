from src.core.routes.v1.endpoints import (
    create_chat_bp,
    create_health_bp,
    create_nlu_bp,
    create_plan_bp,
    create_record_bp,
)
from src.core.routes.v1.websocket import ws_bp


def register_routes(app):
    app.register_blueprint(create_health_bp())
    app.register_blueprint(create_nlu_bp())
    app.register_blueprint(create_record_bp())
    app.register_blueprint(create_plan_bp())
    app.register_blueprint(create_chat_bp())
    app.register_blueprint(ws_bp)


__all__ = ["register_routes"]
