"""
auth.py
-------
Signup / login / logout / "am I logged in" endpoints, as a Flask
Blueprint so app.py doesn't have to grow further.

Deliberately NOT included in this first pass (see the app-wide note in
app.py where this is registered): email verification, password reset,
OAuth providers. Those are separate, real pieces of work -- this is the
minimum needed to give a visitor a persistent identity so custom roles
(and later, saved analyses) can be tied to them instead of a browser
session.
"""

import re

from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from extensions import limiter
from models import db, User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


def _validate_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email or not EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")
    if len(email) > 255:
        raise ValueError("Email address is too long.")
    return email


def _validate_password(password: str) -> str:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > 200:
        raise ValueError("Password is too long.")
    return password


@auth_bp.route("/signup", methods=["POST"])
@limiter.limit("10 per hour")
def signup():
    data = request.get_json(silent=True) or {}
    try:
        email = _validate_email(data.get("email"))
        password = _validate_password(data.get("password"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if User.query.filter_by(email=email).first():
        # Deliberately vague: don't confirm an email is registered to an
        # anonymous caller (basic enumeration-avoidance).
        return jsonify({"error": "Could not create that account. Try logging in instead, or use a different email."}), 400

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return jsonify({"email": user.email})


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        # Same message either way -- don't reveal whether the email exists.
        return jsonify({"error": "Incorrect email or password."}), 401

    login_user(user)
    return jsonify({"email": user.email})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"ok": True})


@auth_bp.route("/me", methods=["GET"])
def me():
    if current_user.is_authenticated:
        return jsonify({"email": current_user.email})
    return jsonify({"email": None})
