"""Checkout (US-07) and the customer's orders (US-08)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.datastructures import MultiDict

from .. import cart, mail, orders
from ..i18n import format_date, t, tr
from ..repositories import orders as orders_repo
from .cart import load as load_cart

bp = Blueprint("orders", __name__)


@bp.route("/order", methods=["GET", "POST"])
@login_required
def checkout():
    c, event_type, lines = load_cart()
    if not event_type or cart.problems(c, event_type, lines):
        flash(t("fix_cart_first"), "error")
        return redirect(url_for("cart.view"))

    allergens, diets = orders_repo.options()
    values, errors = MultiDict(), []
    if request.method == "POST":
        values = request.form
        details, groups, errors = orders.parse_checkout(values, c["guests"], {a["code"] for a in allergens},
                                                        {d["code"] for d in diets})
        if not errors:
            created = orders_repo.create(current_user.email, event_type["id"], c["guests"], c["items"], details,
                                         groups)
            if created is None:
                flash(t("order_failed"), "error")
                return redirect(url_for("cart.view"))
            cart.save({"event_type": None, "guests": None, "items": {}})
            _send_confirmation(created, event_type, c["guests"], details)
            flash(t("order_submitted", id=created["id"]), "success")
            return redirect(url_for("orders.detail", order_id=created["id"]))

    return render_template("checkout.html", event_type=event_type, guests=c["guests"], lines=lines,
                           total=cart.total(lines), allergens=allergens, diets=diets, values=values,
                           errors=errors, earliest=orders.earliest_event_date(), latest=orders.latest_event_date(),
                           lock_days=orders.LOCK_DAYS, group_rows=orders.GUEST_GROUP_ROWS,
                           payment_options=orders.PAYMENT_OPTIONS,
                           more_groups_open=any(v for k, v in values.items(multi=True)
                                                if k.startswith("group-") and not k.startswith("group-1-"))
                           ), (400 if errors else 200)


def _send_confirmation(created: dict, event_type: dict, guests: int, details: dict) -> None:
    body = t("confirmation_body", name=current_user.name, id=created["id"], event=tr(event_type, "name"),
             date=format_date(details["event_date"]), guests=guests, total=created["total_nok"],
             url=url_for("orders.detail", order_id=created["id"], _external=True))
    mail.send(current_user.email, t("confirmation_subject", id=created["id"]), body)


@bp.get("/orders")
@login_required
def history():
    current, past = orders.split_current_past(orders_repo.list_for_customer(current_user.email))
    return render_template("orders.html", current=current, past=past)


@bp.get("/orders/<order_id>")
@login_required
def detail(order_id: str):
    order = orders_repo.get_for_customer(current_user.email, order_id)
    if order is None:
        abort(404)
    return render_template("order.html", order=order, read_only=order["status"] in orders.PAST_STATUSES)
