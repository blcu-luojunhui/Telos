from .api import api_bp
from .websocket import ws_bp


def register_routes(app):
    app.register_blueprint(api_bp)
    app.register_blueprint(ws_bp)


__ALL__ = ["register_routes"]
