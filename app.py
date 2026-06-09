"""Entry point.

``eventlet.monkey_patch()`` MUST be the first import.  Flask-SocketIO's
eventlet worker replaces the standard socket/threading libraries, and the
monkey-patching has to happen before anything else (including Flask) is
imported, otherwise the WebSocket transport falls back to long-polling and
real-time behaviour degrades.
"""
import eventlet

eventlet.monkey_patch()

from website import create_app, socketio  # noqa: E402

app = create_app()


if __name__ == "__main__":
    # ``debug=True`` interacts badly with eventlet's greenlet lifecycle on
    # Werkzeug 3.x (causes an immediate ``wsgi exiting`` and a noisy
    # greenlet-finalizer traceback on shutdown).  Re-enable the reloader
    # manually below if you need it.
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
