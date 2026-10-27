"""Cypher queries for :Order nodes (US-06 – US-08 for customers, US-21 – US-25 for the admin)."""
import secrets

from neo4j.exceptions import ConstraintError

from ..db import run

OPTIONS_QUERY = """
RETURN COLLECT { MATCH (a:Allergen) RETURN a {.code, .name_no, .name_en} ORDER BY a.name_no } AS allergens,
       COLLECT { MATCH (d:Diet) RETURN d {.code, .name_no, .name_en} ORDER BY d.name_no } AS diets
"""

# One query, so the order is created completely or not at all. It checks the minimums again against the database
# (prices and minimums may have changed since the cart page) and copies the minimum and the prices onto the order
# (data_model.md, design choice 1). Returns no row if a check fails.
CREATE_QUERY = """
MATCH (c:Customer {email: $email}) WHERE c.anonymised_at IS NULL
MATCH (e:EventType {id: $event_type_id}) WHERE $guests >= e.min_guests
CALL (e) {
    UNWIND $items AS item
    MATCH (e)<-[:SUITS]-(f:FoodItem {id: item.dish_id, published: true})
    WHERE item.quantity >= CASE WHEN coalesce(f.min_order_qty, 0) > e.min_guests
                                THEN f.min_order_qty ELSE e.min_guests END
    RETURN collect({food: f, quantity: item.quantity}) AS found
}
WITH c, e, found WHERE size(found) = size($items) AND size(found) > 0
CREATE (o:Order {
    id: $order_id, status: 'submitted', payment_status: 'not_paid', payment_option: $payment_option,
    event_date: date($event_date), event_time: $event_time, guests: $guests, min_guests_at_order: e.min_guests,
    delivery_address: $delivery_address, delivery_notes: $delivery_notes,
    total_nok: reduce(total = 0, x IN found | total + x.quantity * x.food.price_nok), created_at: datetime()
})
CREATE (c)-[:PLACED]->(o)-[:FOR_EVENT]->(e)
CREATE (o)-[:HAD_STATUS]->(:StatusChange {to_status: 'submitted', at: datetime(), by_role: 'customer', by_id: c.email})
WITH o, found
CALL (o, found) {
    UNWIND found AS x
    WITH o, x.food AS f, x.quantity AS quantity
    CREATE (o)-[:CONTAINS {quantity: quantity, unit_price_nok: f.price_nok}]->(f)
}
CALL (o) {
    UNWIND $groups AS g
    CREATE (o)-[:HAS_GROUP]->(group:GuestGroup {position: g.position, count: g.count})
    WITH group, g
    CALL (group, g) { MATCH (a:Allergen) WHERE a.code IN g.allergens CREATE (group)-[:HAS_ALLERGY]->(a) }
    CALL (group, g) { MATCH (d:Diet) WHERE d.code IN g.diets CREATE (group)-[:NEEDS_DIET]->(d) }
}
RETURN o.id AS id, o.total_nok AS total_nok
"""

LIST_QUERY = """
MATCH (:Customer {email: $email})-[:PLACED]->(o:Order)-[:FOR_EVENT]->(e:EventType)
RETURN o {.id, .status, .payment_status, .event_date, .event_time, .guests, .total_nok,
          event_type: e {.id, .name_no, .name_en}} AS order
ORDER BY o.event_date, o.event_time, o.created_at
"""

ORDER_PROJECTION = """
o {.*,
    event_type: e {.id, .name_no, .name_en},
    lines: COLLECT {
        MATCH (o)-[line:CONTAINS]->(f:FoodItem)
        RETURN {id: f.id, name_no: f.name_no, name_en: f.name_en, quantity: line.quantity,
                unit_price_nok: line.unit_price_nok, line_total: line.quantity * line.unit_price_nok}
        ORDER BY f.name_no
    },
    groups: COLLECT {
        MATCH (o)-[:HAS_GROUP]->(g:GuestGroup)
        RETURN {position: g.position, count: g.count,
                allergens: COLLECT { MATCH (g)-[:HAS_ALLERGY]->(a:Allergen) RETURN a {.code, .name_no, .name_en} },
                diets: COLLECT { MATCH (g)-[:NEEDS_DIET]->(d:Diet) RETURN d {.code, .name_no, .name_en} }}
        ORDER BY g.position
    },
    history: COLLECT {
        MATCH (o)-[:HAD_STATUS]->(s:StatusChange)
        RETURN s {.from_status, .to_status, .at, .by_role, .by_id, .reason}
        ORDER BY s.at
    }
}
"""

# Only the customer's own orders: the e-mail is part of the match, so another customer's order id gives no row.
DETAIL_QUERY = """
MATCH (:Customer {email: $email})-[:PLACED]->(o:Order {id: $order_id})-[:FOR_EVENT]->(e:EventType)
RETURN """ + ORDER_PROJECTION + " AS order"

# --- customer changes and cancellation (US-09, US-10) ---

# Dishes the customer can choose when changing: the event type's published dishes, plus any already on the order
# (kept at the price they were ordered at, even if the dish has been unpublished since).
CHANGE_OPTIONS_QUERY = """
MATCH (:Customer {email: $email})-[:PLACED]->(o:Order {id: $order_id})-[:FOR_EVENT]->(e:EventType)
RETURN COLLECT {
    MATCH (e)<-[:SUITS]-(f:FoodItem)
    WHERE f.published OR EXISTS { (o)-[:CONTAINS]->(f) }
    OPTIONAL MATCH (o)-[line:CONTAINS]->(f)
    RETURN f {.id, .name_no, .name_en, .min_order_qty, quantity: line.quantity,
              price_nok: coalesce(line.unit_price_nok, f.price_nok)}
    ORDER BY f.name_no
} AS dishes
"""

# Like CREATE_QUERY: one query, re-checks everything against the database, and refuses (no row) when the order is
# locked or no longer changeable. `$lock_until` is the last locked event date (today + LOCK_DAYS, Oslo time).
CHANGE_QUERY = """
MATCH (c:Customer {email: $email})-[:PLACED]->(o:Order {id: $order_id})-[:FOR_EVENT]->(e:EventType)
WHERE o.status IN $changeable AND o.event_date > date($lock_until) AND $guests >= o.min_guests_at_order
WITH c, o, e, COLLECT { MATCH (o)-[old:CONTAINS]->(f:FoodItem) RETURN {id: f.id, price: old.unit_price_nok} } AS old
CALL (o, e, old) {
    UNWIND $items AS item
    MATCH (e)<-[:SUITS]-(f:FoodItem {id: item.dish_id})
    WHERE (f.published OR any(p IN old WHERE p.id = f.id))
      AND item.quantity >= CASE WHEN coalesce(f.min_order_qty, 0) > o.min_guests_at_order
                                THEN f.min_order_qty ELSE o.min_guests_at_order END
    WITH f, item, [p IN old WHERE p.id = f.id | p.price] AS kept
    RETURN collect({food: f, quantity: item.quantity, price: coalesce(kept[0], f.price_nok)}) AS found
}
WITH c, o, found WHERE size(found) = size($items) AND size(found) > 0
CALL (o) { MATCH (o)-[old:CONTAINS]->() DELETE old }
CALL (o) { MATCH (o)-[:HAS_GROUP]->(g:GuestGroup) DETACH DELETE g }
SET o.guests = $guests, o.event_time = $event_time, o.delivery_notes = $delivery_notes, o.changed_at = datetime(),
    o.total_nok = reduce(total = 0, x IN found | total + x.quantity * x.price)
CREATE (o)-[:HAD_STATUS]->(:StatusChange {from_status: o.status, to_status: o.status, at: datetime(),
                                          by_role: 'customer', by_id: c.email})
WITH o, found
CALL (o, found) {
    UNWIND found AS x
    WITH o, x.food AS f, x.quantity AS quantity, x.price AS price
    CREATE (o)-[:CONTAINS {quantity: quantity, unit_price_nok: price}]->(f)
}
CALL (o) {
    UNWIND $groups AS g
    CREATE (o)-[:HAS_GROUP]->(group:GuestGroup {position: g.position, count: g.count})
    WITH group, g
    CALL (group, g) { MATCH (a:Allergen) WHERE a.code IN g.allergens CREATE (group)-[:HAS_ALLERGY]->(a) }
    CALL (group, g) { MATCH (d:Diet) WHERE d.code IN g.diets CREATE (group)-[:NEEDS_DIET]->(d) }
}
RETURN o.id AS id, o.status AS status, o.total_nok AS total_nok
"""

CANCEL_QUERY = """
MATCH (c:Customer {email: $email})-[:PLACED]->(o:Order {id: $order_id})
WHERE o.status IN $changeable AND o.event_date > date($lock_until)
WITH c, o, o.status AS from_status
SET o.status = 'cancelled'
CREATE (o)-[:HAD_STATUS]->(:StatusChange {from_status: from_status, to_status: 'cancelled', at: datetime(),
                                          by_role: 'customer', by_id: c.email})
RETURN o.id AS id, from_status
"""

# --- daily job (US-11, US-25) ---

# Approved orders 7 days or less before the event that haven't had a reminder, and aren't locked yet: a job that
# missed a day still sends it. Marked as sent in the same query, so running the job twice sends one e-mail.
REMINDER_QUERY = """
MATCH (c:Customer)-[:PLACED]->(o:Order {status: 'approved'})-[:FOR_EVENT]->(e:EventType)
WHERE o.reminder_sent_at IS NULL AND date($lock_until) < o.event_date <= date($remind_until)
  AND c.anonymised_at IS NULL
SET o.reminder_sent_at = datetime()
RETURN o {.id, .event_date, .event_time, .guests} AS order, e {.id, .name_no, .name_en} AS event_type,
       c {.email, .name, .language} AS customer
ORDER BY o.event_date
"""

LOCK_QUERY = """
MATCH (o:Order)-[:FOR_EVENT]->(e:EventType)
WHERE o.status IN $changeable AND o.locked_at IS NULL AND o.event_date <= date($lock_until)
SET o.locked_at = datetime()
RETURN o {.id, .status, .event_date, .guests, event_type: e {.id, .name_no, .name_en}} AS order
ORDER BY o.event_date
"""

# --- admin (US-21 – US-25) ---

ADMIN_LIST_QUERY = """
MATCH (c:Customer)-[:PLACED]->(o:Order)-[:FOR_EVENT]->(e:EventType)
WHERE o.status IN $statuses
  AND ($date_from IS NULL OR o.event_date >= date($date_from))
  AND ($date_to IS NULL OR o.event_date <= date($date_to))
CALL (o) {
    OPTIONAL MATCH (x:Order {event_date: o.event_date}) WHERE x.status IN $booked_statuses
    RETURN coalesce(sum(x.guests), 0) AS booked
}
RETURN o {.id, .status, .payment_status, .payment_option, .event_date, .event_time, .guests, .total_nok,
          event_type: e {.id, .name_no, .name_en}, customer: c {.name, .email}, booked_that_day: booked} AS order
ORDER BY o.event_date, o.event_time, o.created_at
LIMIT 500
"""

ADMIN_DETAIL_QUERY = """
MATCH (c:Customer)-[:PLACED]->(o:Order {id: $order_id})-[:FOR_EVENT]->(e:EventType)
RETURN """ + ORDER_PROJECTION + """ AS order, c {.email, .name, .phone, .language} AS customer
"""

# Other approved / in-preparation orders on the same day, for the capacity check (US-23).
CAPACITY_QUERY = """
OPTIONAL MATCH (x:Order {event_date: date($day)})-[:FOR_EVENT]->(e:EventType)
WHERE x.status IN $booked_statuses AND x.id <> $exclude_id
RETURN coalesce(sum(x.guests), 0) AS guests, count(CASE WHEN e.id = $wedding THEN 1 END) > 0 AS wedding
"""

# The WHERE on the current status makes the change safe if two admins click at the same time: the second gets no row.
CHANGE_STATUS_QUERY = """
MATCH (o:Order {id: $order_id}) WHERE o.status = $from_status
MATCH (s:Staff {email: $staff_email})
SET o.status = $to_status
CREATE (o)-[:HAD_STATUS]->(:StatusChange {from_status: $from_status, to_status: $to_status, at: datetime(),
                                          by_role: s.role, by_id: s.email, reason: $reason})
FOREACH (_ IN CASE WHEN $to_status = 'delivered' THEN [1] ELSE [] END |
    CREATE (s)-[:DELIVERED {at: datetime()}]->(o))
RETURN o.id AS id
"""

CHANGE_PAYMENT_QUERY = """
MATCH (o:Order {id: $order_id}) WHERE o.payment_status = $from_status
SET o.payment_status = $to_status, o.payment_changed_at = datetime(), o.payment_changed_by = $staff_email
RETURN o.id AS id
"""




def options() -> tuple[list[dict], list[dict]]:
    """Allergens and diets to choose from for guest groups."""
    rows = run(OPTIONS_QUERY)
    return (rows[0]["allergens"], rows[0]["diets"]) if rows else ([], [])


def new_order_id() -> str:
    return "EM-" + secrets.token_hex(3).upper()


def create(email: str, event_type_id: str, guests: int, items: dict[str, int], details: dict,
           groups: list[dict]) -> dict | None:
    """Create a submitted order. Returns {"id", "total_nok"}, or None if a minimum or a dish no longer holds."""
    params = {
        "email": email, "event_type_id": event_type_id, "guests": guests,
        "items": [{"dish_id": dish_id, "quantity": qty} for dish_id, qty in items.items()],
        "event_date": details["event_date"].isoformat(), "event_time": details["event_time"],
        "payment_option": details["payment_option"],
        "delivery_address": details["delivery_address"], "delivery_notes": details["delivery_notes"],
        "groups": groups,
    }
    for _ in range(3):  # retry on the rare order-id clash (constraint order_id)
        try:
            rows = run(CREATE_QUERY, order_id=new_order_id(), **params)
        except ConstraintError:
            continue
        return rows[0] if rows else None
    raise RuntimeError("could not find a free order id")


def list_for_customer(email: str) -> list[dict]:
    return [r["order"] for r in run(LIST_QUERY, email=email)]


def get_for_customer(email: str, order_id: str) -> dict | None:
    rows = run(DETAIL_QUERY, email=email, order_id=order_id)
    return rows[0]["order"] if rows else None


def admin_list(statuses: list[str], date_from: str | None, date_to: str | None,
               booked_statuses: tuple[str, ...]) -> list[dict]:
    rows = run(ADMIN_LIST_QUERY, statuses=statuses, date_from=date_from, date_to=date_to,
               booked_statuses=list(booked_statuses))
    return [r["order"] for r in rows]


def admin_get(order_id: str) -> tuple[dict | None, dict | None]:
    """(order, customer) for any order, or (None, None)."""
    rows = run(ADMIN_DETAIL_QUERY, order_id=order_id)
    return (rows[0]["order"], rows[0]["customer"]) if rows else (None, None)


def booked_on(day, exclude_id: str, booked_statuses: tuple[str, ...], wedding: str) -> tuple[int, bool]:
    """Guests in other booked orders that day, and whether one of them is a wedding."""
    # str() of a date or a neo4j Date is YYYY-MM-DD.
    rows = run(CAPACITY_QUERY, day=str(day), exclude_id=exclude_id, booked_statuses=list(booked_statuses),
               wedding=wedding)
    return (rows[0]["guests"], rows[0]["wedding"]) if rows else (0, False)


def change_status(order_id: str, from_status: str, to_status: str, staff_email: str, reason: str | None) -> bool:
    return bool(run(CHANGE_STATUS_QUERY, order_id=order_id, from_status=from_status, to_status=to_status,
                    staff_email=staff_email, reason=reason or None))


def change_payment(order_id: str, from_status: str, to_status: str, staff_email: str) -> bool:
    return bool(run(CHANGE_PAYMENT_QUERY, order_id=order_id, from_status=from_status, to_status=to_status,
                    staff_email=staff_email))


def change_options(email: str, order_id: str) -> list[dict]:
    rows = run(CHANGE_OPTIONS_QUERY, email=email, order_id=order_id)
    return rows[0]["dishes"] if rows else []


def change(email: str, order_id: str, change: dict, changeable: tuple[str, ...], lock_until) -> dict | None:
    """Apply a customer's change (US-09). Returns {"id", "status", "total_nok"}, or None if it was refused."""
    rows = run(CHANGE_QUERY, email=email, order_id=order_id, guests=change["guests"], event_time=change["event_time"],
               items=[{"dish_id": d, "quantity": q} for d, q in change["items"].items()],
               delivery_notes=change["delivery_notes"], groups=change["groups"], changeable=list(changeable),
               lock_until=lock_until.isoformat())
    return rows[0] if rows else None


def cancel(email: str, order_id: str, changeable: tuple[str, ...], lock_until) -> str | None:
    """Cancel (US-10). Returns the status the order had, or None if it was refused."""
    rows = run(CANCEL_QUERY, email=email, order_id=order_id, changeable=list(changeable),
               lock_until=lock_until.isoformat())
    return rows[0]["from_status"] if rows else None


def take_reminders(remind_until, lock_until) -> list[dict]:
    """Orders due a reminder, marked as reminded. Each row: {"order", "event_type", "customer"}."""
    return run(REMINDER_QUERY, remind_until=remind_until.isoformat(), lock_until=lock_until.isoformat())


def lock_due(changeable: tuple[str, ...], lock_until) -> list[dict]:
    """Lock orders 5 days or less before the event. Returns the orders locked now."""
    return [r["order"] for r in run(LOCK_QUERY, changeable=list(changeable), lock_until=lock_until.isoformat())]
