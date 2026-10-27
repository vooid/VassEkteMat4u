"""Order rules (US-07, US-08, US-21 – US-25): checkout validation, status groups, admin transitions and capacity.

Pure functions, like cart.py, so they're easy to test. The minimum-order rules are in cart.py and are checked again
in the Cypher that creates the order (repositories/orders.py).
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from werkzeug.datastructures import MultiDict

TIMEZONE = ZoneInfo("Europe/Oslo")
# Orders can be changed or cancelled until more than LOCK_DAYS days before the event (basic_desc.txt). A new order
# must therefore be placed before that too (assumption in US-07, confirm with Ingrid).
LOCK_DAYS = 5
REMINDER_DAYS = 7  # reminder e-mail this many days before the event (basic_desc.txt, US-11)
MAX_DAYS_AHEAD = 730
MAX_TEXT_LENGTH = 500
MAX_QUESTION_LENGTH = 2000
GUEST_GROUP_ROWS = 5  # rows on the checkout form

PAYMENT_OPTIONS = ("invoice", "vipps", "bank_transfer")
CURRENT_STATUSES = ("awaiting_company_approval", "submitted", "approved", "in_preparation")
PAST_STATUSES = ("delivered", "cancelled", "rejected")  # final and read-only (state_order.md)
ALL_STATUSES = CURRENT_STATUSES + PAST_STATUSES
PAYMENT_STATUSES = ("not_paid", "invoiced", "paid")

# What the Ekte Mat admin may do, from the allowed-transitions table in docs/diagrams/state_order.md.
# Company approval and customer changes/cancellations are not admin transitions.
ADMIN_TRANSITIONS = {
    "submitted": ("approved", "rejected"),
    "approved": ("in_preparation",),  # only when locked, see admin_actions()
    "in_preparation": ("delivered",),
}
PAYMENT_TRANSITIONS = {"not_paid": ("invoiced", "paid"), "invoiced": ("paid",)}  # payment state diagram

# Covers per day (Sunniva interview): 400, or 250 when a served wedding dinner is booked that day.
CAPACITY = 400
CAPACITY_WEDDING_DAY = 250
WEDDING = "wedding"
BOOKED_STATUSES = ("approved", "in_preparation")  # count against capacity


def today() -> date:
    return datetime.now(TIMEZONE).date()


def earliest_event_date(on: date | None = None) -> date:
    return (on or today()) + timedelta(days=LOCK_DAYS + 1)


def latest_event_date(on: date | None = None) -> date:
    return (on or today()) + timedelta(days=MAX_DAYS_AHEAD)


def _native(value):
    """neo4j.time.Date -> datetime.date."""
    return value.to_native() if hasattr(value, "to_native") else value


def is_locked(event_date, on: date | None = None) -> bool:
    """5 days or less before the event: no more customer changes, and the admin can release it to the kitchen."""
    return (_native(event_date) - (on or today())).days <= LOCK_DAYS


def lock_until(on: date | None = None) -> date:
    """Events on or before this date are locked."""
    return (on or today()) + timedelta(days=LOCK_DAYS)


def last_change_date(event_date) -> date:
    """The last day the customer can change or cancel: more than LOCK_DAYS days before the event."""
    return _native(event_date) - timedelta(days=LOCK_DAYS + 1)


# Customers may change or cancel these until the lock. Cancelling a *submitted* order is an assumption
# (open question 1 in state_order.md): nothing has been approved yet, so we let the customer withdraw it.
CUSTOMER_CHANGEABLE = ("submitted", "approved")


def customer_can_change(order: dict, on: date | None = None) -> bool:
    return order["status"] in CUSTOMER_CHANGEABLE and not is_locked(order["event_date"], on)


def parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _parse_count(value) -> int | None:
    try:
        n = int(str(value).strip())
    except ValueError:
        return None
    return n if n >= 1 else None


def parse_checkout(form, guests: int, allergen_codes: set[str], diet_codes: set[str],
                   on: date | None = None) -> tuple[dict, list[dict], list[tuple[str, dict]]]:
    """Read the checkout form (a werkzeug MultiDict). Returns (details, guest groups, errors as (i18n key, args)).

    """
    errors = []
    details = {
        "event_date": parse_date(form.get("event_date", "")),
        "delivery_address": form.get("delivery_address", "").strip(),
        "delivery_notes": form.get("delivery_notes", "").strip(),
        "payment_option": form.get("payment_option", ""),
    }

    event_date = details["event_date"]
    if event_date is None:
        errors.append(("event_date_invalid", {}))
    elif event_date < earliest_event_date(on):
        errors.append(("event_date_too_soon", {"days": LOCK_DAYS, "date": earliest_event_date(on)}))
    elif event_date > latest_event_date(on):
        errors.append(("event_date_too_far", {}))
    if not details["delivery_address"]:
        errors.append(("address_required", {}))
    if max(len(details["delivery_address"]), len(details["delivery_notes"])) > MAX_TEXT_LENGTH:
        errors.append(("text_too_long", {"max": MAX_TEXT_LENGTH}))
    if details["payment_option"] not in PAYMENT_OPTIONS:
        errors.append(("payment_option_required", {}))

    groups, group_errors = parse_guest_groups(form, guests, allergen_codes, diet_codes)
    errors.extend(group_errors)

    return details, groups, errors


def parse_guest_groups(form, guests: int, allergen_codes: set[str],
                       diet_codes: set[str]) -> tuple[list[dict], list[tuple[str, dict]]]:
    """Guest-group rows of the checkout and change forms. Rows are "count + allergies/diets", never names
    (GDPR art. 9, data_model.md). A row with no count and nothing ticked is ignored."""
    errors = []
    groups = []
    for n in range(1, GUEST_GROUP_ROWS + 1):
        raw_count = form.get(f"group-{n}-count", "").strip()
        allergens = [c for c in form.getlist(f"group-{n}-allergens") if c in allergen_codes]
        diets = [c for c in form.getlist(f"group-{n}-diets") if c in diet_codes]
        if not raw_count and not allergens and not diets:
            continue
        count = _parse_count(raw_count)
        if count is None:
            errors.append(("group_count_invalid", {"n": n}))
        elif not allergens and not diets:
            errors.append(("group_needs_something", {"n": n}))
        else:
            groups.append({"position": n, "count": count, "allergens": allergens, "diets": diets})
    if sum(g["count"] for g in groups) > guests:
        errors.append(("groups_exceed_guests", {"n": guests}))
    return groups, errors


def groups_as_form(groups: list[dict]) -> MultiDict:
    """Saved guest groups as form values, to fill in the change form."""
    values = MultiDict()
    for n, g in enumerate(groups, start=1):
        values.add(f"group-{n}-count", str(g["count"]))
        for a in g["allergens"]:
            values.add(f"group-{n}-allergens", a["code"])
        for d in g["diets"]:
            values.add(f"group-{n}-diets", d["code"])
    return values


def split_current_past(orders: list[dict]) -> tuple[list[dict], list[dict]]:
    """Current orders soonest first, past orders most recent first. `orders` must be sorted by event date."""
    current = [o for o in orders if o["status"] in CURRENT_STATUSES]
    past = [o for o in orders if o["status"] not in CURRENT_STATUSES]
    return current, past[::-1]


def admin_actions(order: dict, on: date | None = None) -> tuple[str, ...]:
    """Statuses the admin can move this order to now."""
    allowed = ADMIN_TRANSITIONS.get(order["status"], ())
    if "in_preparation" in allowed and not is_locked(order["event_date"], on):
        allowed = tuple(s for s in allowed if s != "in_preparation")
    return allowed


def payment_actions(order: dict) -> tuple[str, ...]:
    """Payment statuses the admin can set now. Not on rejected or cancelled orders: nothing is owed."""
    if order["status"] in ("rejected", "cancelled"):
        return ()
    return PAYMENT_TRANSITIONS.get(order["payment_status"], ())


def status_change_error(order: dict, to_status: str, reason: str, on: date | None = None) -> str | None:
    """i18n key of why the admin can't make this change, or None."""
    if to_status not in admin_actions(order, on):
        return "change_not_allowed"
    if to_status == "rejected" and not reason:
        return "reason_required"
    if len(reason) > MAX_TEXT_LENGTH:
        return "reason_too_long"
    return None


def capacity(booked_guests: int, wedding_booked: bool, order: dict) -> dict:
    """Guests that day if this order counts too, against the day's limit (US-23). `booked_guests` and
    `wedding_booked` are for the other approved / in-preparation orders that day."""
    is_wedding = order["event_type"]["id"] == WEDDING
    limit = CAPACITY_WEDDING_DAY if wedding_booked or is_wedding else CAPACITY
    total = booked_guests + order["guests"]
    return {"booked": booked_guests, "total": total, "limit": limit, "over": total > limit}


def parse_change(form, order: dict, dishes: list[dict], allergen_codes: set[str],
                 diet_codes: set[str]) -> tuple[dict, list[tuple[str, dict]]]:
    """Read the change form (US-09). `dishes` are the ones the customer may choose (repositories/orders.py
    `change_options`). Returns ({guests, items, delivery_notes, groups}, errors).

    The minimums are the ones saved on the order, not the event type's current minimum (US-06, US-09).
    """
    errors = []
    minimum = order["min_guests_at_order"]
    guests = _parse_count(form.get("guests", ""))
    if guests is None or guests > 9999:
        errors.append(("guests_missing", {}))
    elif guests < minimum:
        errors.append(("guests_below_saved_minimum", {"n": minimum}))

    items = {}
    for dish in dishes:
        raw = form.get(f"qty-{dish['id']}", "").strip()
        if raw in ("", "0"):
            continue
        qty = _parse_count(raw)
        dish_min = max(minimum, dish.get("min_order_qty") or 0)
        if qty is None or qty > 9999:
            errors.append(("invalid_quantity", {"max": 9999}))
        elif qty < dish_min:
            errors.append(("dish_below_minimum", {"dish_id": dish["id"], "n": dish_min}))
        else:
            items[dish["id"]] = qty
    if not items and not any(k == "dish_below_minimum" for k, _ in errors):
        errors.append(("order_needs_a_dish", {}))

    notes = form.get("delivery_notes", "").strip()
    if len(notes) > MAX_TEXT_LENGTH:
        errors.append(("text_too_long", {"max": MAX_TEXT_LENGTH}))
    groups, group_errors = parse_guest_groups(form, guests or 0, allergen_codes, diet_codes)
    errors.extend(group_errors)
    return {"guests": guests, "items": items, "delivery_notes": notes, "groups": groups}, errors


def question_error(text: str) -> str | None:
    """Questions and answers (US-12, US-26): not empty, not endless."""
    if not text:
        return "question_empty"
    if len(text) > MAX_QUESTION_LENGTH:
        return "question_too_long"
    return None
