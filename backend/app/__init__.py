"""Ekte Mat backend: Flask app factory."""
from flask import Flask

from . import db
from .config import Config
from .routes.event_types import bp as event_types_bp
from .routes.health import bp as health_bp


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(event_types_bp, url_prefix="/api/event-types")
    return app
