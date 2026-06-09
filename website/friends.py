"""Friend requests: request, accept, decline, cancel, unfriend."""
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import Friendship, User

friends = Blueprint("friends", __name__)


@friends.route("/friends")
@login_required
def friends_list():
    my_friends = current_user.friends()
    # Incoming: pending requests where I am the addressee.
    incoming = (
        Friendship.query.filter_by(addressee_id=current_user.id, status="pending")
        .order_by(Friendship.created_at.desc())
        .all()
    )
    # Outgoing: pending requests I sent.
    outgoing = (
        Friendship.query.filter_by(requester_id=current_user.id, status="pending")
        .order_by(Friendship.created_at.desc())
        .all()
    )
    return render_template(
        "friends/friends.html",
        my_friends=my_friends,
        incoming=incoming,
        outgoing=outgoing,
    )


@friends.route("/friends/request/<int:user_id>", methods=["POST"])
@login_required
def request_friend(user_id: int):
    if user_id == current_user.id:
        flash("You cannot friend yourself.", "warning")
        return redirect(url_for("views.home"))

    target = db.session.get(User, user_id)
    if target is None:
        abort(404)

    # Look for any existing row either direction.
    existing = (
        Friendship.query.filter(
            (
                (Friendship.requester_id == current_user.id)
                & (Friendship.addressee_id == user_id)
            )
            | (
                (Friendship.requester_id == user_id)
                & (Friendship.addressee_id == current_user.id)
            )
        ).first()
    )
    if existing is not None:
        if existing.status == "accepted":
            flash(f"You are already friends with {target.username}.", "info")
        elif existing.status == "pending":
            flash("A friend request is already pending.", "info")
        else:  # declined
            flash(
                "A previous request was declined. They would need to send a new one.",
                "warning",
            )
        return redirect(url_for("views.profile", username=target.username))

    row = Friendship(
        requester_id=current_user.id,
        addressee_id=user_id,
        status="pending",
    )
    db.session.add(row)
    db.session.commit()
    flash(f"Friend request sent to {target.username}.", "success")
    return redirect(url_for("views.profile", username=target.username))


def _load_incoming(friendship_id: int) -> Friendship:
    row = db.session.get(Friendship, friendship_id)
    if row is None or row.addressee_id != current_user.id or row.status != "pending":
        abort(404)
    return row


@friends.route("/friends/accept/<int:friendship_id>", methods=["POST"])
@login_required
def accept_friend(friendship_id: int):
    row = _load_incoming(friendship_id)
    row.status = "accepted"
    db.session.commit()
    requester = db.session.get(User, row.requester_id)
    flash(f"You are now friends with {requester.username}.", "success")
    return redirect(url_for("friends.friends_list"))


@friends.route("/friends/decline/<int:friendship_id>", methods=["POST"])
@login_required
def decline_friend(friendship_id: int):
    row = _load_incoming(friendship_id)
    row.status = "declined"
    db.session.commit()
    flash("Friend request declined.", "info")
    return redirect(url_for("friends.friends_list"))


@friends.route("/friends/cancel/<int:friendship_id>", methods=["POST"])
@login_required
def cancel_friend(friendship_id: int):
    row = db.session.get(Friendship, friendship_id)
    if (
        row is None
        or row.requester_id != current_user.id
        or row.status != "pending"
    ):
        abort(404)
    db.session.delete(row)
    db.session.commit()
    flash("Friend request cancelled.", "info")
    return redirect(url_for("friends.friends_list"))


@friends.route("/friends/unfriend/<int:user_id>", methods=["POST"])
@login_required
def unfriend(user_id: int):
    if user_id == current_user.id:
        abort(400)
    row = Friendship.query.filter(
        Friendship.status == "accepted",
        (
            (Friendship.requester_id == current_user.id)
            & (Friendship.addressee_id == user_id)
        )
        | (
            (Friendship.requester_id == user_id)
            & (Friendship.addressee_id == current_user.id)
        ),
    ).first()
    if row is None:
        flash("You are not friends with that user.", "warning")
        return redirect(url_for("friends.friends_list"))
    db.session.delete(row)
    db.session.commit()
    flash("Unfriended.", "info")
    return redirect(url_for("friends.friends_list"))
