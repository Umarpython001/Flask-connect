"""SQLAlchemy models for the social app.

A single ``Message`` table holds both private DMs and group-room messages; the
``room_id`` column is a string.  For 1-on-1 DMs the value is the deterministic
key returned by :func:`website.utils.deterministic_dm_room_id`
(e.g. ``"dm:1:2"``); for group rooms it is ``"room:<pk>"``.
"""
from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # Stored path is relative to ``static/`` so it can be passed straight to
    # ``url_for("static", filename=...)``.
    profile_pic = db.Column(
        db.String(255),
        nullable=False,
        default="uploads/images/default_avatar.svg",
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship(
        "Post", backref="author", lazy=True, cascade="all, delete-orphan"
    )
    sent_messages = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        backref="sender",
        lazy=True,
        cascade="all, delete-orphan",
    )
    room_memberships = db.relationship(
        "RoomMembership", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    friend_requests_sent = db.relationship(
        "Friendship",
        foreign_keys="Friendship.requester_id",
        backref="requester",
        lazy=True,
        cascade="all, delete-orphan",
    )
    friend_requests_received = db.relationship(
        "Friendship",
        foreign_keys="Friendship.addressee_id",
        backref="addressee",
        lazy=True,
        cascade="all, delete-orphan",
    )

    # ----- password helpers ---------------------------------------------------
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    # ----- friendship helpers -------------------------------------------------
    def _accepted_friendships(self):
        return Friendship.query.filter(
            Friendship.status == "accepted",
            (
                (Friendship.requester_id == self.id)
                | (Friendship.addressee_id == self.id)
            ),
        )

    def friends(self):
        """Return a list of accepted friend ``User`` objects."""
        fships = self._accepted_friendships().all()
        other_ids = [
            f.addressee_id if f.requester_id == self.id else f.requester_id
            for f in fships
        ]
        if not other_ids:
            return []
        return User.query.filter(User.id.in_(other_ids)).order_by(User.username).all()

    def is_friend_with(self, other_id: int) -> bool:
        fships = self._accepted_friendships().filter(
            (
                (Friendship.requester_id == self.id)
                & (Friendship.addressee_id == other_id)
            )
            | (
                (Friendship.requester_id == other_id)
                & (Friendship.addressee_id == self.id)
            )
        ).first()
        return fships is not None

    def _outgoing_row(self, other_id: int):
        return Friendship.query.filter_by(
            requester_id=self.id, addressee_id=other_id
        ).first()

    def _incoming_row(self, other_id: int):
        return Friendship.query.filter_by(
            requester_id=other_id, addressee_id=self.id
        ).first()

    def has_outgoing_pending_to(self, other_id: int) -> bool:
        row = self._outgoing_row(other_id)
        return row is not None and row.status == "pending"

    def has_incoming_pending_from(self, other_id: int) -> bool:
        row = self._incoming_row(other_id)
        return row is not None and row.status == "pending"

    def friendship_status_with(self, other_id: int) -> str:
        """Return one of ``"self"``, ``"accepted"``, ``"outgoing_pending"``,
        ``"incoming_pending"``, ``"declined"``, ``"none"``."""
        if other_id == self.id:
            return "self"
        if self.is_friend_with(other_id):
            return "accepted"
        out = self._outgoing_row(other_id)
        if out is not None and out.status == "pending":
            return "outgoing_pending"
        inn = self._incoming_row(other_id)
        if inn is not None and inn.status == "pending":
            return "incoming_pending"
        if (out is not None and out.status == "declined") or (
            inn is not None and inn.status == "declined"
        ):
            return "declined"
        return "none"


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Path relative to ``static/``.
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # String key shared with the Socket.IO room name; see module docstring.
    room_id = db.Column(db.String(80), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Room(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    creator_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship("User", foreign_keys=[creator_id])
    memberships = db.relationship(
        "RoomMembership", backref="room", lazy=True, cascade="all, delete-orphan"
    )

    def members(self):
        """Return the list of member ``User`` objects (joined)."""
        if not self.memberships:
            return []
        return (
            User.query.join(RoomMembership, RoomMembership.user_id == User.id)
            .filter(RoomMembership.room_id == self.id)
            .order_by(User.username)
            .all()
        )


class RoomMembership(db.Model):
    __tablename__ = "room_memberships"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_user"),
    )


class Friendship(db.Model):
    __tablename__ = "friendships"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    addressee_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friend_pair"),
        CheckConstraint("requester_id <> addressee_id", name="ck_not_self_friend"),
    )
