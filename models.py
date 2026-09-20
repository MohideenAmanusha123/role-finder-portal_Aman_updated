"""
models.py
---------
SQLAlchemy models for user accounts and per-account custom roles.

Design notes:
- Passwords are never stored in plaintext -- only a Werkzeug-generated hash.
- CustomRole rows replace the session-based custom-role storage (see
  app.py's _session_roles()) ONLY for logged-in users. Anonymous visitors
  keep using the session, exactly as before this feature existed -- this
  is additive, not a breaking change.
- Skills are stored as a JSON-encoded list in a Text column rather than a
  separate join table, matching the simple shape roles_data.py already
  uses elsewhere (a role is a name + a flat skill list). If roles grow
  more structure later (required vs. preferred with different weights
  per user, say), this is the natural place to normalize further.
"""

import json
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    custom_roles = db.relationship(
        "CustomRole", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def custom_roles_dict(self) -> dict:
        """Shape matches roles_data.ROLES / merge_roles(): {name: info_dict}."""
        return {role.name: role.to_role_info() for role in self.custom_roles}


class CustomRole(db.Model):
    __tablename__ = "custom_roles"
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_custom_role_per_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(500), nullable=False, default="")
    skills_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def skills(self) -> list:
        try:
            return json.loads(self.skills_json)
        except (TypeError, ValueError):
            return []

    @skills.setter
    def skills(self, value: list) -> None:
        self.skills_json = json.dumps(list(value))

    def to_role_info(self) -> dict:
        """Same shape roles_data.build_custom_role() returns, so this can
        be merged into the role catalog exactly like a session-stored one.
        """
        skills = self.skills
        return {
            "description": self.description,
            "level": "mid",
            "required": skills,
            "preferred": [],
            "skills": skills,
            "custom": True,
        }
