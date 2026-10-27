"""Shopping cart (US-05) and minimum-order rules (US-06).

The cart lives in the session, so it survives logging in. An order is for one event type, so the cart is too:
    session["cart"] = {"event_type": "wedding", "guests": 60, "items": {"layer-cake": 60}}
Rules are pure functions so they're easy to test and to reuse when the order is submitted (feature 4).
"""
from flask import session

MAX_QUANTITY = 9999  # sanity limit for guests and portions


def get() -> dict:
    cart = session.get("cart") or {}
    return {"event_type": cart.get("event_type"), "guests": cart.get("guests"), "items": dict(cart.get("items", {}))}


def save(cart: dict) -> None:
    if not cart["items"]:
        session.pop("cart", None)
    else:
        session["cart"] = cart


def item_count() -> int:
    return len(get()["items"])


def dish_minimum(event_type: dict, dish: dict) -> int:
    """Minimum portions of a dish: the event type's current minimum or the dish's own minimum, whichever is larger.
    Same rule as the menu cards (repositories/menu.py)."""
    return max(event_type["min_guests"], dish.get("min_order_qty") or 0)


def parse_quantity(value) -> int | None:
    """A whole number from 1 to MAX_QUANTITY, or None."""
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= MAX_QUANTITY else None


def lines(cart: dict, event_type: dict, dishes: list[dict]) -> list[dict]:
    """Cart lines with price, minimum and line total, in the cart's order. Dishes missing from `dishes`
    (unpublished or no longer on this event type's menu) are left out."""
    by_id = {d["id"]: d for d in dishes}
    result = []
    for dish_id, qty in cart["items"].items():
        dish = by_id.get(dish_id)
        if dish:
            result.append({**dish, "quantity": qty, "minimum": dish_minimum(event_type, dish),
                           "line_total": qty * dish["price_nok"]})
    return result


def total(cart_lines: list[dict]) -> int:
    return sum(line["line_total"] for line in cart_lines)


def problems(cart: dict, event_type: dict, cart_lines: list[dict]) -> list[tuple[str, dict]]:
    """Reasons the cart can't be ordered yet, as (i18n key, format args). Empty list = OK to order."""
    found = []
    if not cart_lines:
        found.append(("cart_empty", {}))
        return found
    guests = cart.get("guests")
    if guests is None:
        found.append(("guests_missing", {}))
    elif guests < event_type["min_guests"]:
        found.append(("guests_below_minimum", {"n": event_type["min_guests"]}))
    for line in cart_lines:
        if line["quantity"] < line["minimum"]:
            found.append(("dish_below_minimum", {"dish_id": line["id"], "n": line["minimum"]}))
    return found
