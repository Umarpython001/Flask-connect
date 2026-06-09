"""Main site navigation: home feed, profile pages."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Post, User
from .utils import save_image

views = Blueprint("views", __name__)


@views.route("/")
@login_required
def home():
    # Newest 50 posts, joined to author for the byline.
    posts = (
        Post.query.order_by(Post.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("views/home.html", posts=posts)


@views.route("/profile/<username>")
@login_required
def profile(username: str):
    user = User.query.filter_by(username=username).first()
    if user is None:
        abort(404)
    posts = (
        Post.query.filter_by(user_id=user.id)
        .order_by(Post.created_at.desc())
        .all()
    )
    friendship_status = user.friendship_status_with(current_user.id)
    return render_template(
        "views/profile.html",
        profile_user=user,
        posts=posts,
        friendship_status=friendship_status,
    )


@views.route("/u/<int:user_id>")
@login_required
def user_redirect(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    return redirect(url_for("views.profile", username=user.username))


@views.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = current_user
    if request.method == "POST":
        action = request.form.get("action", "avatar")
        if action == "avatar":
            pic = request.files.get("profile_pic")
            if pic and pic.filename:
                try:
                    new_path = save_image(pic, "profile_pics")
                    user.profile_pic = new_path
                    db.session.commit()
                    flash("Profile picture updated.", "success")
                except ValueError as e:
                    flash(str(e), "danger")
            else:
                flash("Please choose an image to upload.", "warning")
        elif action == "password":
            current_pw = request.form.get("current_password") or ""
            new_pw = request.form.get("new_password") or ""
            confirm = request.form.get("confirm_password") or ""
            if not user.check_password(current_pw):
                flash("Current password is incorrect.", "danger")
            elif len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "danger")
            elif new_pw != confirm:
                flash("New passwords do not match.", "danger")
            else:
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                flash("Password updated.", "success")
        return redirect(url_for("views.edit_profile"))
    return render_template("views/edit_profile.html", profile_user=user)
