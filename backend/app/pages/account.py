"""Register, log in and log out (US-04)."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .. import auth
from ..i18n import current_language, t
from ..repositories import customers
from ..repositories import staff as staff_repo
from ..urls import safe_next

bp = Blueprint("account", __name__)


def _after_login(customer: auth.Customer) -> None:
    login_user(customer)
    # The account's language wins over the anonymous session's (US-02).
    if customer.language:
        session["lang"] = customer.language


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("menu.index"))
    form = {"name": "", "email": "", "phone": ""}
    errors = []
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("name", "email", "phone")}
        form["email"] = auth.normalise_email(form["email"])
        password, password2 = request.form.get("password", ""), request.form.get("password2", "")
        errors = auth.registration_errors(form["email"], password, password2, form["name"])
        if not errors:
            created = customers.create(form["email"], auth.hash_password(password), form["name"],
                                       form["phone"], current_language())
            if created is None:
                errors = [("email_taken", {})]
            else:
                _after_login(auth.Customer(created))
                flash(t("welcome", name=created["name"]), "success")
                return redirect(safe_next(request.args.get("next")))
    return render_template("register.html", form=form, errors=errors, next=request.args.get("next", "")), \
        (400 if errors else 200)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("menu.index"))
    email = ""
    failed = False
    if request.method == "POST":
        email = auth.normalise_email(request.form.get("email"))
        customer = auth.authenticate(email, request.form.get("password", ""))
        if customer:
            _after_login(customer)
            flash(t("logged_in", name=customer.name), "success")
            return redirect(safe_next(request.args.get("next")))
        failed = True
    return render_template("login.html", email=email, failed=failed, next=request.args.get("next", "")), \
        (401 if failed else 200)


@bp.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    """Login for Ekte Mat staff (admin, kitchen, driver). Accounts are made with `flask create-staff`."""
    if current_user.is_authenticated and current_user.is_staff:
        return redirect(url_for(auth.home_endpoint(current_user)))
    email = ""
    failed = False
    if request.method == "POST":
        email = auth.normalise_email(request.form.get("email"))
        member = auth.authenticate_staff(email, request.form.get("password", ""))
        if member:
            return _staff_logged_in(member)
        failed = True
    return render_template("staff_login.html", email=email, failed=failed, next=request.args.get("next", "")), \
        (401 if failed else 200)


def _staff_logged_in(member: auth.Staff):
    # A customer session in the same browser is replaced, cart included.
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    login_user(member)
    flash(t("logged_in", name=member.name), "success")
    return redirect(safe_next(request.args.get("next"), auth.home_endpoint(member)))


@bp.route("/staff/pin", methods=["GET", "POST"])
def pin_login():
    """PIN login for the kitchen tablet and drivers' phones (US-27): pick your name, type your PIN.
    Only on devices an admin has approved (/admin/devices); elsewhere staff use the password login."""
    if current_user.is_authenticated and current_user.is_staff:
        return redirect(url_for(auth.home_endpoint(current_user)))
    if auth.pin_device(touch=request.method == "POST") is None:
        return render_template("pin_login.html", device_ok=False, next=request.args.get("next", "")), 403
    error = None
    chosen = ""
    if request.method == "POST":
        chosen = request.form.get("email", "")
        member, blocked = auth.authenticate_pin(chosen, request.form.get("pin", ""))
        if member:
            return _staff_logged_in(member)
        error = "pin_blocked" if blocked else "pin_failed"
    return render_template("pin_login.html", device_ok=True, users=staff_repo.pin_users(auth.PIN_ROLES), chosen=chosen,
                           error=error, lock_minutes=auth.PIN_LOCK_MINUTES,
                           next=request.args.get("next", "")), (401 if error else 200)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    # Keep the language, drop everything else (including the cart).
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    flash(t("logged_out"), "success")
    return redirect(url_for("menu.index"))
