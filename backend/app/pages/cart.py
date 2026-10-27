"""HTML pages for the shopping cart (US-05) and the minimum check (US-06)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import cart
from ..i18n import t
from ..repositories import cart as cart_repo

bp = Blueprint("cart", __name__, url_prefix="/cart")


def _load():
    """The cart from the session, its event type and lines. Removes dishes that are no longer available."""
    c = cart.get()
    if not c["items"]:
        return c, None, []
    event_type, dishes = cart_repo.event_type_with_dishes(c["event_type"], list(c["items"]))
    if event_type is None:
        cart.save({"event_type": None, "guests": None, "items": {}})
        flash(t("cart_unavailable_removed"), "warning")
        return cart.get(), None, []
    lines = cart.lines(c, event_type, dishes)
    if len(lines) < len(c["items"]):
        c["items"] = {line["id"]: line["quantity"] for line in lines}
        cart.save(c)
        flash(t("cart_unavailable_removed"), "warning")
    return c, event_type, lines


@bp.get("")
def view():
    c, event_type, lines = _load()
    problems = cart.problems(c, event_type, lines) if event_type else [("cart_empty", {})]
    return render_template("cart.html", cart=c, event_type=event_type, lines=lines,
                           total=cart.total(lines), problems=problems)


@bp.post("/add")
def add():
    event_type_id = request.form.get("event_type", "")
    dish_id = request.form.get("dish", "")
    menu_anchor = url_for("menu.index", _anchor=event_type_id)
    qty = cart.parse_quantity(request.form.get("quantity"))
    if qty is None:
        flash(t("invalid_quantity", max=cart.MAX_QUANTITY), "error")
        return redirect(menu_anchor)

    c = cart.get()
    if c["items"] and c["event_type"] != event_type_id:
        flash(t("cart_other_event_type"), "error")
        return redirect(menu_anchor)

    event_type, dishes = cart_repo.event_type_with_dishes(event_type_id, [dish_id])
    if event_type is None or not dishes:
        flash(t("dish_unavailable"), "error")
        return redirect(url_for("menu.index"))

    c["event_type"] = event_type_id
    c["items"][dish_id] = min(c["items"].get(dish_id, 0) + qty, cart.MAX_QUANTITY)
    cart.save(c)
    flash(t("added_to_cart", qty=qty), "success")
    return redirect(menu_anchor)


@bp.post("/update")
def update():
    c = cart.get()
    invalid = False
    guests_raw = request.form.get("guests", "").strip()
    if guests_raw:
        guests = cart.parse_quantity(guests_raw)
        if guests is None:
            invalid = True
        else:
            c["guests"] = guests
    for dish_id in list(c["items"]):
        raw = request.form.get(f"qty-{dish_id}")
        if raw is None:
            continue
        qty = cart.parse_quantity(raw)
        if qty is None:
            invalid = True
        else:
            c["items"][dish_id] = qty
    cart.save(c)
    flash(t("invalid_quantity", max=cart.MAX_QUANTITY) if invalid else t("cart_updated"),
          "error" if invalid else "success")
    return redirect(url_for("cart.view"))


@bp.post("/remove/<dish_id>")
def remove(dish_id: str):
    c = cart.get()
    c["items"].pop(dish_id, None)
    cart.save(c)
    return redirect(url_for("cart.view"))


@bp.post("/clear")
def clear():
    cart.save({"event_type": None, "guests": None, "items": {}})
    return redirect(url_for("cart.view"))
