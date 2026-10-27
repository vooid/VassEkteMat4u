"""HTML pages for the public menu (US-01) and language switch (US-02)."""
from urllib.parse import urlparse

from flask import Blueprint, redirect, render_template, request, session, url_for

from ..i18n import LANGUAGES
from ..repositories import menu

bp = Blueprint("menu", __name__)


@bp.get("/")
def index():
    return render_template("menu.html", event_types=menu.menu_by_event_type())


@bp.post("/language/<lang>")
def set_language(lang: str):
    if lang in LANGUAGES:
        session["lang"] = lang
    # Only redirect back within this site.
    target = request.form.get("next", "")
    if not target.startswith("/") or target.startswith("//") or urlparse(target).netloc:
        target = url_for("menu.index")
    return redirect(target)
