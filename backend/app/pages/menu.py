"""HTML pages for the public menu (US-01) and language switch (US-02)."""
from flask import Blueprint, redirect, render_template, request, session
from flask_login import current_user

from ..i18n import LANGUAGES
from ..repositories import customers, menu
from ..urls import safe_next

bp = Blueprint("menu", __name__)


@bp.get("/")
def index():
    return render_template("menu.html", event_types=menu.menu_by_event_type())


@bp.post("/language/<lang>")
def set_language(lang: str):
    if lang in LANGUAGES:
        session["lang"] = lang
        if current_user.is_authenticated and not current_user.is_staff:
            customers.set_language(current_user.email, lang)  # US-02: saved on the account
    return redirect(safe_next(request.form.get("next")))
