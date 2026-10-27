"""Customer login (US-04): Flask-Login sessions, Werkzeug password hashes.

Basic login only: no password reset by e-mail in this version (decision 2026-10-27).
"""
import re

from flask import Flask
from flask_login import LoginManager, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .repositories import customers

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
# Checked when the e-mail doesn't exist, so a failed login takes as long whether or not the account exists.
_DUMMY_HASH = generate_password_hash("not-a-real-password")

login_manager = LoginManager()
login_manager.login_view = "account.login"
login_manager.login_message = "login_required"  # i18n key, translated by localize_callback in init_app
login_manager.login_message_category = "warning"


class Customer(UserMixin):
    def __init__(self, data: dict):
        self.email = data["email"]
        self.name = data.get("name", "")
        self.language = data.get("language")

    def get_id(self) -> str:
        # Prefixed so staff accounts (feature 5) can share the same login session.
        return f"customer:{self.email}"


@login_manager.user_loader
def load_user(user_id: str):
    kind, _, key = user_id.partition(":")
    if kind == "customer":
        data = customers.get(key)
        return Customer(data) if data else None
    return None


def normalise_email(email: str | None) -> str:
    return (email or "").strip().lower()


def registration_errors(email: str, password: str, password2: str, name: str) -> list[tuple[str, dict]]:
    """Validation problems as (i18n key, args); empty if the form is OK."""
    errors = []
    if not name.strip():
        errors.append(("name_required", {}))
    if len(email) > 254 or not EMAIL_RE.match(email):
        errors.append(("email_invalid", {}))
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        errors.append(("password_length", {"min": MIN_PASSWORD_LENGTH, "max": MAX_PASSWORD_LENGTH}))
    elif password != password2:
        errors.append(("passwords_differ", {}))
    return errors


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def authenticate(email: str, password: str) -> Customer | None:
    data = customers.get_with_hash(email)
    if data is None:
        check_password_hash(_DUMMY_HASH, password)
        return None
    return Customer(data) if check_password_hash(data["password_hash"], password) else None


def init_app(app: Flask) -> None:
    from .i18n import t
    login_manager.localize_callback = t
    login_manager.init_app(app)
