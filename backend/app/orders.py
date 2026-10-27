"""Order rules (US-07, US-08): checkout validation and status groups.

Pure functions, like cart.py, so they're easy to test. The minimum-order rules are in cart.py and are checked again
in the Cypher that creates the order (repositories/orders.py).
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Europe/Oslo")
# Orders can be changed or cancelled until more than LOCK_DAYS days before the event (basic_desc.txt). A new order
# must therefore be placed before that too (assumption in US-07, confirm with Ingrid).
LOCK_DAYS = 5
MAX_DAYS_AHEAD = 730
MAX_TEXT_LENGTH = 500
GUEST_GROUP_ROWS = 5  # rows on the checkout form

PAYMENT_OPTIONS = ("invoice", "vipps", "bank_transfer")
CURRENT_STATUSES = ("awaiting_company_approval", "submitted", "approved", "in_preparation")
PAST_STATUSES = ("delivered", "cancelled", "rejected")  # final and read-only (state_order.md)


def today() -> date:
    return datetime.now(TIMEZONE).date()


def earliest_event_date(on: date | None = None) -> date:
    return (on or today()) + timedelta(days=LOCK_DAYS + 1)


def latest_event_date(on: date | None = None) -> date:
    return (on or today()) + timedelta(days=MAX_DAYS_AHEAD)


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

    Guest groups are rows of "count + allergies/diets", never names (GDPR art. 9, data_model.md). A row with no
    count and nothing ticked is ignored.
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

    return details, groups, errors


def split_current_past(orders: list[dict]) -> tuple[list[dict], list[dict]]:
    """Current orders soonest first, past orders most recent first. `orders` must be sorted by event date."""
    current = [o for o in orders if o["status"] in CURRENT_STATUSES]
    past = [o for o in orders if o["status"] not in CURRENT_STATUSES]
    return current, past[::-1]
