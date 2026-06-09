"""Direct messages (1-on-1) and the SocketIO handlers that power both DMs
and group rooms.

The HTTP routes here:
    GET  /dm                       — list of conversations
    GET  /dm/<other_id>            — render the 1-on-1 chat UI
    GET  /api/dm/<other_id>/history  — JSON history for a DM
    GET  /api/room/<id>/history      — JSON history for a group room

The SocketIO event handlers (``@socketio.on(...)``) live at the bottom of
this file.  A single namespace ``/`` is used; events are prefixed ``dm:`` or
``room:`` to keep them namespaced.
"""
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user
from flask_socketio import emit, join_room

from .extensions import db, socketio
from .models import Message, Room, RoomMembership, User
from .utils import deterministic_dm_room_id, group_room_key

dm = Blueprint("dm", __name__)


# --------------------------------------------------------------------- helpers
def _serialize_message(msg: Message) -> dict:
    return {
        "id": msg.id,
        "room_id": msg.room_id,
        "sender_id": msg.sender_id,
        "sender_username": msg.sender.username if msg.sender else "",
        "body": msg.body,
        "created_at": msg.created_at.isoformat() + "Z" if msg.created_at else None,
    }


def _fetch_dm_history(other_id: int, before: int | None, limit: int = 50):
    room_key = deterministic_dm_room_id(current_user.id, other_id)
    q = Message.query.filter_by(room_id=room_key)
    if before:
        q = q.filter(Message.id < before)
    msgs = q.order_by(Message.id.desc()).limit(limit).all()
    return list(reversed(msgs)), room_key


# ---------------------------------------------------------------- HTTP routes
@dm.route("/dm")
@dm.route("/dm/")
def list_dms():
    # DMs are open to any logged-in user, but we still need a logged-in user.
    if not current_user.is_authenticated:
        from flask_login import login_required

        # Defer to Flask-Login's redirect by re-invoking the view.
        return login_required(list_dms)()
    me = current_user.id
    # All DM room_ids the user is a participant in (either as sender or
    # implicitly by appearing as the other party in a row).
    dm_rooms = (
        db.session.query(Message.room_id)
        .filter(Message.room_id.like("dm:%"))
        .filter(
            (Message.sender_id == me)
            | Message.room_id.like(f"dm:{me}:%")
            | Message.room_id.like(f"dm:%:{me}")
        )
        .distinct()
        .subquery()
    )
    rows = (
        db.session.query(Message.room_id, Message.body, Message.created_at)
        .filter(Message.room_id.in_(dm_rooms))
        .order_by(Message.id.desc())
        .all()
    )
    seen: dict[str, dict] = {}
    for r in rows:
        if r.room_id in seen:
            continue
        seen[r.room_id] = {"room_id": r.room_id, "body": r.body, "created_at": r.created_at}
    # Resolve the other party for each dm room.
    conversations = []
    for room_key, info in seen.items():
        try:
            _, lo, hi = room_key.split(":")
            other_id = int(hi) if int(lo) == me else int(lo)
        except ValueError:
            continue
        other = db.session.get(User, other_id)
        if other is None:
            continue
        conversations.append({"other": other, "preview": info["body"], "ts": info["created_at"]})
    conversations.sort(key=lambda c: c["ts"] or datetime.min, reverse=True)
    return render_template("dm/dm_list.html", conversations=conversations)


@dm.route("/dm/<int:other_id>")
def dm_room(other_id: int):
    if not current_user.is_authenticated:
        from flask_login import login_required

        return login_required(dm_room)(other_id=other_id)
    other = db.session.get(User, other_id)
    if other is None:
        abort(404)
    return render_template("dm/dm_room.html", other=other)


@dm.route("/api/dm/<int:other_id>/history")
def dm_history_api(other_id: int):
    if not current_user.is_authenticated:
        from flask_login import login_required

        return login_required(dm_history_api)(other_id=other_id)
    before = request.args.get("before", type=int)
    msgs, room_key = _fetch_dm_history(other_id, before, limit=50)
    return jsonify({"room_id": room_key, "messages": [_serialize_message(m) for m in msgs]})


@dm.route("/api/room/<int:room_id>/members-list")
def room_members_api(room_id: int):
    if not current_user.is_authenticated:
        from flask_login import login_required

        return login_required(room_members_api)(room_id=room_id)
    if RoomMembership.query.filter_by(
        room_id=room_id, user_id=current_user.id
    ).first() is None:
        abort(403)
    room = db.session.get(Room, room_id)
    if room is None:
        abort(404)
    return jsonify(
        {
            "members": [
                {
                    "id": m.id,
                    "username": m.username,
                    "profile_pic": m.profile_pic,
                }
                for m in room.members()
            ]
        }
    )


@dm.route("/api/room/<int:room_id>/history")
def room_history_api(room_id: int):
    if not current_user.is_authenticated:
        from flask_login import login_required

        return login_required(room_history_api)(room_id=room_id)
    if RoomMembership.query.filter_by(
        room_id=room_id, user_id=current_user.id
    ).first() is None:
        abort(403)
    room_key = group_room_key(room_id)
    q = Message.query.filter_by(room_id=room_key)
    before = request.args.get("before", type=int)
    if before:
        q = q.filter(Message.id < before)
    msgs = q.order_by(Message.id.desc()).limit(50).all()
    return jsonify(
        {
            "room_id": room_key,
            "messages": [_serialize_message(m) for m in reversed(msgs)],
        }
    )


# ---------------------------------------------------------------- SocketIO
MAX_MESSAGE_BODY = 2000


@socketio.on("connect")
def _on_connect():
    """Reject anonymous SocketIO connections; Flask-Login's session cookie
    is sent on the upgrade request automatically."""
    if not current_user.is_authenticated:
        return False  # reject


def _save_and_broadcast(room_key: str, body: str) -> Message:
    body = (body or "").strip()
    if not body:
        raise ValueError("Empty message.")
    if len(body) > MAX_MESSAGE_BODY:
        raise ValueError(f"Message too long (max {MAX_MESSAGE_BODY} chars).")
    msg = Message(sender_id=current_user.id, room_id=room_key, body=body)
    db.session.add(msg)
    db.session.commit()
    payload = _serialize_message(msg)
    emit("dm:message", payload, to=room_key)
    return msg


@socketio.on("dm:join")
def _on_dm_join(data):
    other_id = (data or {}).get("other_id")
    if not isinstance(other_id, int):
        return
    other = db.session.get(User, other_id)
    if other is None:
        return
    room_key = deterministic_dm_room_id(current_user.id, other_id)
    join_room(room_key)
    emit(
        "dm:joined",
        {
            "room_id": room_key,
            "other": {
                "id": other.id,
                "username": other.username,
                "profile_pic": other.profile_pic,
            },
        },
    )


@socketio.on("dm:send")
def _on_dm_send(data):
    payload = data or {}
    other_id = payload.get("other_id")
    body = payload.get("body") or ""
    if not isinstance(other_id, int):
        return
    try:
        room_key = deterministic_dm_room_id(current_user.id, other_id)
        _save_and_broadcast(room_key, body)
    except ValueError:
        return


@socketio.on("dm:typing")
def _on_dm_typing(data):
    payload = data or {}
    other_id = payload.get("other_id")
    typing = bool(payload.get("typing"))
    if not isinstance(other_id, int):
        return
    other = db.session.get(User, other_id)
    if other is None:
        return
    # Broadcast on the dm room itself.  The sender's own client filters on
    # ``from_id`` (it sees their own typing events echoed back).
    room_key = deterministic_dm_room_id(current_user.id, other_id)
    emit(
        "dm:typing_broadcast",
        {"from_id": current_user.id, "from_username": current_user.username, "typing": typing},
        to=room_key,
    )


@socketio.on("room:join")
def _on_room_join(data):
    room_id = (data or {}).get("room_id")
    if not isinstance(room_id, int):
        return
    if RoomMembership.query.filter_by(
        room_id=room_id, user_id=current_user.id
    ).first() is None:
        return
    room = db.session.get(Room, room_id)
    if room is None:
        return
    key = group_room_key(room_id)
    join_room(key)
    members = [
        {
            "id": m.id,
            "username": m.username,
            "profile_pic": m.profile_pic,
        }
        for m in room.members()
    ]
    emit(
        "room:joined",
        {"room_id": room_id, "name": room.name, "members": members},
    )


@socketio.on("room:send")
def _on_room_send(data):
    payload = data or {}
    room_id = payload.get("room_id")
    body = payload.get("body") or ""
    if not isinstance(room_id, int):
        return
    if RoomMembership.query.filter_by(
        room_id=room_id, user_id=current_user.id
    ).first() is None:
        return
    try:
        msg = Message(sender_id=current_user.id, room_id=group_room_key(room_id), body=body.strip())
        if not msg.body:
            return
        if len(msg.body) > MAX_MESSAGE_BODY:
            return
        db.session.add(msg)
        db.session.commit()
        emit("room:message", _serialize_message(msg), to=group_room_key(room_id))
    except Exception:
        db.session.rollback()
        return


@socketio.on("room:typing")
def _on_room_typing(data):
    payload = data or {}
    room_id = payload.get("room_id")
    typing = bool(payload.get("typing"))
    if not isinstance(room_id, int):
        return
    if RoomMembership.query.filter_by(
        room_id=room_id, user_id=current_user.id
    ).first() is None:
        return
    emit(
        "room:typing_broadcast",
        {
            "room_id": room_id,
            "from_id": current_user.id,
            "from_username": current_user.username,
            "typing": typing,
        },
        to=group_room_key(room_id),
    )
