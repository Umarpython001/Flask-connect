"""Signup / login / logout."""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from .extensions import db
from .models import User
from .utils import EMAIL_RE, save_image

auth = Blueprint("auth", __name__)

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _username_ok(name: str) -> bool:
    return bool(name and _USERNAME_RE.match(name))


def _validate_signup(form) -> tuple[list[str], dict]:
    """Return ``(errors, cleaned)`` for a signup form submission."""
    errors: list[str] = []
    username = (form.get("username") or "").strip()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    confirm = form.get("confirm") or ""

    if not (3 <= len(username) <= 40):
        errors.append("Username must be 3-40 characters.")
    if not _username_ok(username):
        errors.append("Username may only contain letters, numbers, and underscores.")
    if not EMAIL_RE.match(email):
        errors.append("Please enter a valid email address.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm:
        errors.append("Passwords do not match.")
    if username and User.query.filter_by(username=username).first():
        errors.append("That username is already taken.")
    if email and User.query.filter_by(email=email).first():
        errors.append("That email is already registered.")

    return errors, {
        "username": username,
        "email": email,
        "password": password,
    }


@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("views.home"))
    if request.method == "POST":
        errors, cleaned = _validate_signup(request.form)
        profile_pic_path = "uploads/images/default_avatar.svg"
        pic = request.files.get("profile_pic")
        if pic and pic.filename:
            try:
                profile_pic_path = save_image(pic, "profile_pics")
            except ValueError as e:
                errors.append(str(e))
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "auth/signup.html",
                username=cleaned["username"],
                email=cleaned["email"],
            )
        user = User(
            username=cleaned["username"],
            email=cleaned["email"],
            profile_pic=profile_pic_path,
        )
        user.set_password(cleaned["password"])
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"Welcome, {user.username}!", "success")
        return redirect(url_for("views.home"))
    return render_template("auth/signup.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("views.home"))
    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))
        user = User.query.filter(
            or_(User.username == identifier, User.email == identifier.lower())
        ).first()
        if user is None or not user.check_password(password):
            flash("Invalid username/email or password.", "danger")
            return render_template("auth/login.html", identifier=identifier)
        login_user(user, remember=remember)
        flash(f"Welcome back, {user.username}.", "success")
        next_url = request.args.get("next") or url_for("views.home")
        return redirect(next_url)
    return render_template("auth/login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
