"""Small helpers shared across blueprints."""
import os
import re
import secrets

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

# Allowlist of file extensions (lowercase, no dot).
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
# Whitelist of corresponding MIME types as reported by the browser.
ALLOWED_MIMETYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
}
# 5 MB upper bound on a single upload (matches MAX_CONTENT_LENGTH in app
# config).  Kept here so error messages can reference it.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Minimal email shape check (not RFC-compliant; just enough to catch typos).
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def deterministic_dm_room_id(a, b) -> str:
    """Return the canonical 1-on-1 room id for users ``a`` and ``b``.

    Sorting the ids guarantees the same string regardless of which user
    "initiates" the conversation, so the same pair of users always lands in
    the same room and the message history is unified.
    """
    lo, hi = sorted((int(a), int(b)))
    return f"dm:{lo}:{hi}"


def group_room_key(room_id) -> str:
    """Return the canonical SocketIO/Message room key for a group room pk."""
    return f"room:{int(room_id)}"


def save_image(file_storage: FileStorage, subdir: str) -> str:
    """Validate, rename, and persist ``file_storage`` under
    ``static/uploads/<subdir>/`` and return the path **relative to
    ``static/``** for storage in the DB.

    Raises :class:`ValueError` with a human-readable message on any failure
    (bad extension, bad mimetype, empty file).
    """
    if file_storage is None or not file_storage.filename:
        raise ValueError("No file selected.")

    original = secure_filename(file_storage.filename)
    if not original or "." not in original:
        raise ValueError("Invalid filename.")
    ext = original.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Allowed: "
            + ", ".join(sorted(ALLOWED_EXTENSIONS))
        )
    mimetype = (file_storage.mimetype or "").lower()
    if mimetype not in ALLOWED_MIMETYPES:
        raise ValueError("Unsupported file content type.")

    upload_root = current_app.config["UPLOAD_ROOT"]
    target_dir = os.path.join(upload_root, subdir)
    os.makedirs(target_dir, exist_ok=True)

    new_name = f"{secrets.token_hex(8)}.{ext}"
    abs_path = os.path.join(target_dir, new_name)
    file_storage.save(abs_path)

    # Return path relative to ``static/`` for url_for("static", ...).
    static_root = current_app.static_folder
    rel = os.path.relpath(abs_path, static_root).replace(os.sep, "/")
    return rel
