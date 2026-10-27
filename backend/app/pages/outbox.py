"""Development e-mail outbox (see mail.py). Only registered when DEV_OUTBOX is on: it shows every customer's mail."""
from flask import Blueprint, render_template

from ..repositories import outbox

bp = Blueprint("outbox", __name__, url_prefix="/dev/outbox")


@bp.get("")
def index():
    return render_template("outbox.html", messages=outbox.latest())
