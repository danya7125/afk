import logging

from flask import Flask

from .config import Config
from .db import init_pool
from .repositories.chat_history import ChatHistoryRepository
from .routes.api import api_bp
from .routes.web import web_bp


def create_app(config_object=Config) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_object)

    logging.basicConfig(
        level=app.config.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    with app.app_context():
        init_pool()
        ChatHistoryRepository().ensure_table()

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app