"""Group chat rooms: create, list, view, add/remove members, leave."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db, socketio
from .models import Room, RoomMembership, User
from .utils import group_room_key

rooms = Blueprint("rooms", __name__)


def _user_rooms():
    return (
        Room.query.join(RoomMembership, RoomMembership.room_id == Room.id)
        .filter(RoomMembership.user_id == current_user.id)
        .order_by(Room.created_at.desc())
        .all()
    )


@rooms.route("/rooms")
@login_required
def list_rooms():
    return render_template("rooms/room_list.html", rooms=_user_rooms())


@rooms.route("/rooms/create", methods=["GET", "POST"])
@login_required
def create_room():
    my_friends = current_user.friends()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        member_ids = request.form.getlist("member_ids", type=int)
        if not name:
            flash("Room name is required.", "warning")
            return render_template(
                "rooms/room_create.html", friends=my_friends, name=name
            )
        if len(name) > 80:
            flash("Room name is too long (max 80 characters).", "warning")
            return render_template(
                "rooms/room_create.html", friends=my_friends, name=name
            )

        room = Room(name=name, creator_id=current_user.id)
        db.session.add(room)
        db.session.flush()  # so room.id is available

        # Creator auto-included.
        db.session.add(RoomMembership(room_id=room.id, user_id=current_user.id))

        # Only friends can be added.
        friend_ids = {f.id for f in my_friends}
        for uid in member_ids:
            if uid == current_user.id:
                continue
            if uid not in friend_ids:
                continue  # silently drop non-friend ids
            db.session.add(RoomMembership(room_id=room.id, user_id=uid))

        db.session.commit()
        flash(f"Room “{room.name}” created.", "success")
        return redirect(url_for("rooms.view_room", room_id=room.id))

    return render_template("rooms/room_create.html", friends=my_friends, name="")


@rooms.route("/rooms/<int:room_id>")
@login_required
def view_room(room_id: int):
    room = db.session.get(Room, room_id)
    if room is None:
        abort(404)
    is_member = RoomMembership.query.filter_by(
        room_id=room_id, user_id=current_user.id
    ).first() is not None
    if not is_member:
        abort(403)
    members = room.members()
    creator = db.session.get(User, room.creator_id) if room.creator_id else None
    return render_template(
        "rooms/room.html",
        room=room,
        members=members,
        is_creator=(room.creator_id == current_user.id),
        creator=creator,
    )


@rooms.route("/rooms/<int:room_id>/add", methods=["POST"])
@login_required
def add_member(room_id: int):
    room = db.session.get(Room, room_id)
    if room is None:
        abort(404)
    if room.creator_id != current_user.id:
        abort(403)

    target_id = request.form.get("user_id", type=int)
    if target_id is None:
        flash("No user specified.", "warning")
        return redirect(url_for("rooms.view_room", room_id=room_id))

    target = db.session.get(User, target_id)
    if target is None:
        flash("User not found.", "warning")
        return redirect(url_for("rooms.view_room", room_id=room_id))

    if not current_user.is_friend_with(target_id):
        flash(f"You can only add friends to the room. {target.username} is not your friend.", "danger")
        return redirect(url_for("rooms.view_room", room_id=room_id))

    existing = RoomMembership.query.filter_by(
        room_id=room_id, user_id=target_id
    ).first()
    if existing is not None:
        flash(f"{target.username} is already in the room.", "info")
        return redirect(url_for("rooms.view_room", room_id=room_id))

    db.session.add(RoomMembership(room_id=room_id, user_id=target_id))
    db.session.commit()
    flash(f"Added {target.username} to the room.", "success")

    # Notify connected members.
    socketio.emit(
        "room:user_joined",
        {"room_id": room_id, "user": {"id": target.id, "username": target.username}},
        to=group_room_key(room_id),
    )
    return redirect(url_for("rooms.view_room", room_id=room_id))


@rooms.route("/rooms/<int:room_id>/remove/<int:user_id>", methods=["POST"])
@login_required
def remove_member(room_id: int, user_id: int):
    room = db.session.get(Room, room_id)
    if room is None:
        abort(404)
    if room.creator_id != current_user.id:
        abort(403)
    if user_id == current_user.id:
        flash("You cannot remove yourself; leave the room instead.", "warning")
        return redirect(url_for("rooms.view_room", room_id=room_id))

    membership = RoomMembership.query.filter_by(
        room_id=room_id, user_id=user_id
    ).first()
    if membership is None:
        flash("That user is not in the room.", "info")
        return redirect(url_for("rooms.view_room", room_id=room_id))

    db.session.delete(membership)
    db.session.commit()
    target = db.session.get(User, user_id)
    flash(f"Removed {target.username if target else 'user'} from the room.", "info")
    socketio.emit(
        "room:user_left",
        {"room_id": room_id, "user_id": user_id},
        to=group_room_key(room_id),
    )
    return redirect(url_for("rooms.view_room", room_id=room_id))


@rooms.route("/rooms/<int:room_id>/leave", methods=["POST"])
@login_required
def leave_room(room_id: int):
    room = db.session.get(Room, room_id)
    if room is None:
        abort(404)
    if room.creator_id == current_user.id:
        flash("Room creators cannot leave; remove all members or ask an admin to delete the room.", "warning")
        return redirect(url_for("rooms.view_room", room_id=room_id))

    membership = RoomMembership.query.filter_by(
        room_id=room_id, user_id=current_user.id
    ).first()
    if membership is None:
        return redirect(url_for("rooms.list_rooms"))

    db.session.delete(membership)
    db.session.commit()
    flash(f"Left the room “{room.name}”.", "info")
    socketio.emit(
        "room:user_left",
        {"room_id": room_id, "user_id": current_user.id},
        to=group_room_key(room_id),
    )
    return redirect(url_for("rooms.list_rooms"))
