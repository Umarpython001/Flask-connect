"""Flask application factory.

Wires up the SQLAlchemy database, Flask-Login, Flask-SocketIO, all
blueprints, and a one-shot ``db.create_all()`` to bootstrap the schema.
"""
import os

from flask import Flask
from flask_login import LoginManager

from .extensions import db, login_manager, socketio

# A small whitelist of Blueprint import paths so a typo doesn't silently
# drop a route.  Add new blueprints here.
BLUEPRINTS = (
    "website.auth:auth",
    "website.views:views",
    "website.posts:posts",
    "website.friends:friends",
    "website.rooms:rooms",
    "website.dm:dm",
)


def create_app() -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        template_folder="templates",
    )

    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "social.db")

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{db_path}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 MB upload cap
    )
    app.config["UPLOAD_ROOT"] = os.path.join(app.static_folder, "uploads")

    # Bind extensions to the app.
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"
    socketio.init_app(app)

    # Register blueprints.
    for bp_path in BLUEPRINTS:
        mod_name, attr = bp_path.split(":")
        module = __import__(mod_name, fromlist=[attr])
        app.register_blueprint(getattr(module, attr))

    # Lazy import to avoid pulling in models before db.init_app.
    from . import models  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    # Bootstrap schema.  With no migrations library in the stack, this is the
    # simplest reliable approach for v1.
    with app.app_context():
        db.create_all()

    return app
