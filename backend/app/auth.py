"""Login for customers (US-04) and Ekte Mat staff: Flask-Login sessions, Werkzeug password hashes.

Basic login only: no password reset by e-mail in this version (decision 2026-10-27). Customers and staff are separate
node labels with separate login pages, so customer self-registration can never create an admin (data_model.md).
"""
import hashlib
import re
import secrets
from functools import wraps

from flask import Flask, abort, jsonify, redirect, request, url_for
from flask_login import LoginManager, UserMixin, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from .repositories import customers, devices, staff

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
STAFF_ROLES = ("admin", "kitchen", "driver")
# Kitchen and driver staff may log in with a short PIN (Mateo: no long passwords with flour on your hands).
# Admins always use their password: they can change orders and minimums.
PIN_ROLES = ("kitchen", "driver")
PIN_RE = re.compile(r"^\d{4,8}$")
MAX_PIN_ATTEMPTS = 5
PIN_LOCK_MINUTES = 15
# PIN login only works on devices an admin has approved (the kitchen tablet, the drivers' phones): the approval is a
# random token in a long-lived cookie. An IP allow-list wouldn't do, because drivers are on mobile data.
PIN_DEVICE_COOKIE = "ektemat_pin_device"
PIN_DEVICE_DAYS = 365
# Where each role lands after logging in.
HOME_ENDPOINTS = {"admin": "admin.order_list", "kitchen": "kitchen.index", "driver": "driver.index"}
# Checked when the e-mail doesn't exist, so a failed login takes as long whether or not the account exists.
_DUMMY_HASH = generate_password_hash("not-a-real-password")

login_manager = LoginManager()
login_manager.login_view = "account.login"
login_manager.login_message = "login_required"  # i18n key, translated by localize_callback in init_app
login_manager.login_message_category = "warning"


class Customer(UserMixin):
    is_staff = False

    def __init__(self, data: dict):
        self.email = data["email"]
        self.name = data.get("name", "")
        self.language = data.get("language")

    def get_id(self) -> str:
        return f"customer:{self.email}"


class Staff(UserMixin):
    is_staff = True

    def __init__(self, data: dict):
        self.email = data["email"]
        self.name = data.get("name", "")
        self.role = data["role"]

    def get_id(self) -> str:
        return f"staff:{self.email}"


@login_manager.user_loader
def load_user(user_id: str):
    kind, _, key = user_id.partition(":")
    if kind == "customer":
        data = customers.get(key)
        return Customer(data) if data else None
    if kind == "staff":
        data = staff.get(key)
        return Staff(data) if data else None
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
    errors.extend(password_errors(password, password2))
    return errors


def password_errors(password: str, password2: str) -> list[tuple[str, dict]]:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        return [("password_length", {"min": MIN_PASSWORD_LENGTH, "max": MAX_PASSWORD_LENGTH})]
    if password != password2:
        return [("passwords_differ", {})]
    return []


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def _password_matches(data: dict | None, password: str) -> bool:
    if data is None:
        check_password_hash(_DUMMY_HASH, password)
        return False
    return check_password_hash(data["password_hash"], password)


def authenticate(email: str, password: str) -> Customer | None:
    data = customers.get_with_hash(email)
    return Customer(data) if _password_matches(data, password) else None


def authenticate_staff(email: str, password: str) -> Staff | None:
    data = staff.get_with_hash(email)
    return Staff(data) if _password_matches(data, password) else None


def authenticate_pin(email: str, pin: str) -> tuple[Staff | None, bool]:
    """(staff member or None, blocked). A short PIN is easy to guess, so after MAX_PIN_ATTEMPTS wrong PINs in a row
    that account's PIN login is blocked for PIN_LOCK_MINUTES."""
    data = staff.get_with_pin(email, PIN_ROLES)
    if data is None:
        check_password_hash(_DUMMY_HASH, pin)
        return None, False
    if data["locked"]:
        return None, True
    if check_password_hash(data["pin_hash"], pin):
        staff.pin_succeeded(email)
        return Staff(data), False
    staff.pin_failed(email, MAX_PIN_ATTEMPTS, PIN_LOCK_MINUTES)
    return None, False


def new_device_token() -> tuple[str, str]:
    """(token for the cookie, hash for the database)."""
    token = secrets.token_urlsafe(32)
    return token, device_token_hash(token)


def device_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def pin_device(touch: bool = False) -> dict | None:
    """The approved device this request comes from, or None."""
    token = request.cookies.get(PIN_DEVICE_COOKIE)
    return devices.find(device_token_hash(token), touch) if token else None


def home_endpoint(member: Staff) -> str:
    return HOME_ENDPOINTS.get(member.role, "menu.index")


def customer_required(view):
    """Logged in as a customer. Staff get 403: they don't place orders with their staff account."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.is_staff:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def staff_required(*roles: str):
    """Logged in as staff with one of `roles`. Anonymous visitors go to the staff login, others get 403."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("account.staff_login", next=request.full_path.rstrip("?")))
            if not current_user.is_staff or current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def api_staff_required(*roles: str):
    """Like staff_required, for the JSON API: 401/403 with a JSON error instead of a redirect."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify(error="login required"), 401
            if not current_user.is_staff or current_user.role not in roles:
                return jsonify(error="not allowed"), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


def init_app(app: Flask) -> None:
    from .i18n import t
    login_manager.localize_callback = t
    login_manager.init_app(app)
