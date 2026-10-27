"""Ekte Mat backend: Flask app factory."""
from flask import Flask
from flask_wtf.csrf import CSRFProtect

from . import auth, cart, db, i18n
from .config import Config
from .pages.account import bp as account_page_bp
from .pages.cart import bp as cart_page_bp
from .pages.menu import bp as menu_page_bp
from .routes.event_types import bp as event_types_bp
from .routes.health import bp as health_bp


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)
    i18n.init_app(app)
    auth.init_app(app)
    app.register_blueprint(menu_page_bp)
    app.register_blueprint(cart_page_bp)
    app.register_blueprint(account_page_bp)
    app.context_processor(lambda: {"cart_count": cart.item_count()})

    # Every HTML form must send csrf_token(). The JSON API is exempt for now; it gets its own auth later.
    csrf = CSRFProtect(app)
    csrf.exempt(event_types_bp)
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(event_types_bp, url_prefix="/api/event-types")
    return app
