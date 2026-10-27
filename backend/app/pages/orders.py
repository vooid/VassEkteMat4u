"""Checkout (US-07), the customer's orders (US-08), changing (US-09) and cancelling (US-10)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.datastructures import MultiDict

from .. import cart, mail, orders
from ..auth import customer_required
from ..i18n import format_date, t, t_in, tr
from ..repositories import orders as orders_repo
from .cart import load as load_cart

bp = Blueprint("orders", __name__)


@bp.route("/order", methods=["GET", "POST"])
@customer_required
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
@customer_required
def history():
    current, past = orders.split_current_past(orders_repo.list_for_customer(current_user.email))
    return render_template("orders.html", current=current, past=past)


@bp.get("/orders/<order_id>")
@customer_required
def detail(order_id: str):
    order = orders_repo.get_for_customer(current_user.email, order_id)
    if order is None:
        abort(404)
    return render_template("order.html", order=order, read_only=order["status"] in orders.PAST_STATUSES,
                           can_change=orders.customer_can_change(order),
                           last_change_date=orders.last_change_date(order["event_date"]), lock_days=orders.LOCK_DAYS)


def _load_changeable(order_id: str) -> dict | None:
    """The customer's order if it can still be changed or cancelled; otherwise flash why and return None."""
    order = orders_repo.get_for_customer(current_user.email, order_id)
    if order is None:
        abort(404)
    if not orders.customer_can_change(order):
        flash(t("order_not_changeable", days=orders.LOCK_DAYS), "error")
        return None
    return order


@bp.route("/orders/<order_id>/change", methods=["GET", "POST"])
@customer_required
def change(order_id: str):
    order = _load_changeable(order_id)
    if order is None:
        return redirect(url_for("orders.detail", order_id=order_id))
    dishes = orders_repo.change_options(current_user.email, order_id)
    allergens, diets = orders_repo.options()
    errors = []
    if request.method == "POST":
        values = request.form
        parsed, errors = orders.parse_change(values, order, dishes, {a["code"] for a in allergens},
                                             {d["code"] for d in diets})
        if not errors:
            result = orders_repo.change(current_user.email, order_id, parsed, orders.CUSTOMER_CHANGEABLE,
                                        orders.lock_until())
            if result is None:
                flash(t("order_change_refused"), "error")
                return redirect(url_for("orders.detail", order_id=order_id))
            if result["status"] == "approved":  # US-09: the admin must know the approved order changed
                _notify_admins("mail_admin_changed", order, guests=parsed["guests"], total=result["total_nok"])
            flash(t("order_changed"), "success")
            return redirect(url_for("orders.detail", order_id=order_id))
    else:
        values = orders.groups_as_form(order["groups"])
        values.add("guests", str(order["guests"]))
        values.add("delivery_notes", order.get("delivery_notes") or "")
        for line in order["lines"]:
            values.add(f"qty-{line['id']}", str(line["quantity"]))
    for dish in dishes:
        dish["minimum"] = max(order["min_guests_at_order"], dish.get("min_order_qty") or 0)
    return render_template("order_change.html", order=order, dishes=dishes, allergens=allergens, diets=diets,
                           values=values, errors=errors, group_rows=orders.GUEST_GROUP_ROWS,
                           more_groups_open=any(v for k, v in values.items(multi=True)
                                                if k.startswith("group-") and not k.startswith("group-1-")),
                           last_change_date=orders.last_change_date(order["event_date"])
                           ), (400 if errors else 200)


@bp.post("/orders/<order_id>/cancel")
@customer_required
def cancel(order_id: str):
    order = _load_changeable(order_id)
    if order is None:
        return redirect(url_for("orders.detail", order_id=order_id))
    if request.form.get("confirm") != "yes":
        flash(t("cancel_confirm_needed"), "error")
        return redirect(url_for("orders.detail", order_id=order_id))
    if orders_repo.cancel(current_user.email, order_id, orders.CUSTOMER_CHANGEABLE, orders.lock_until()) is None:
        flash(t("order_change_refused"), "error")
        return redirect(url_for("orders.detail", order_id=order_id))
    _notify_admins("mail_admin_cancelled", order)
    mail.send(current_user.email, t("mail_cancelled_subject", id=order_id),
              t("mail_cancelled_body", name=current_user.name, id=order_id, event=tr(order["event_type"], "name"),
                date=format_date(order["event_date"]),
                url=url_for("orders.detail", order_id=order_id, _external=True)))
    flash(t("order_cancelled", id=order_id), "success")
    return redirect(url_for("orders.detail", order_id=order_id))


def _notify_admins(key: str, order: dict, **kwargs) -> None:
    """Admin e-mails are in Norwegian, whatever language the customer uses."""
    args = {"id": order["id"], "customer": current_user.name, "email": current_user.email,
            "event": order["event_type"]["name_no"], "date": format_date(order["event_date"], "no"),
            "url": url_for("admin.order_detail", order_id=order["id"], _external=True), **kwargs}
    mail.send_to_admins(t_in("no", key + "_subject", **args), t_in("no", key + "_body", **args))
