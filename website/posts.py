"""Post creation and deletion (image only, per v1 spec)."""
import os

from flask import Blueprint, abort, current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import Post
from .utils import save_image

posts = Blueprint("posts", __name__)


@posts.route("/create-post", methods=["POST"])
@login_required
def create_post():
    pic = request.files.get("image")
    if not pic or not pic.filename:
        flash("Please choose an image to post.", "warning")
        return redirect(request.referrer or url_for("views.home"))
    try:
        rel_path = save_image(pic, "user_posts")
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(request.referrer or url_for("views.home"))

    post = Post(user_id=current_user.id, image_path=rel_path)
    db.session.add(post)
    db.session.commit()
    flash("Post shared!", "success")
    return redirect(url_for("views.home"))


@posts.route("/delete-post/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id: int):
    post = db.session.get(Post, post_id)
    if post is None:
        abort(404)
    if post.user_id != current_user.id:
        abort(403)

    # Best-effort filesystem cleanup.  Ignore OSError.
    try:
        abs_path = os.path.join(current_app.static_folder, post.image_path)
        if os.path.isfile(abs_path):
            os.remove(abs_path)
    except OSError:
        pass

    db.session.delete(post)
    db.session.commit()
    flash("Post removed.", "info")
    return redirect(
        request.referrer or url_for("views.profile", username=current_user.username)
    )
