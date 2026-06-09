"""Shared Flask extension singletons.

These are declared here (without an app) and bound to the app inside the
``create_app`` factory in ``website/__init__.py``.  Splitting them out keeps
``models.py`` and the blueprints free of circular imports.
"""
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
# ``async_mode="eventlet"`` matches the eventlet worker monkey-patched in
# ``app.py``.  ``cors_allowed_origins="*"`` is fine for local dev; tighten in
# production.
socketio = SocketIO(async_mode="eventlet", cors_allowed_origins="*")
