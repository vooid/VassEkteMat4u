"""Cypher queries for the kitchen screen (US-27, US-28), the prep list (US-29) and the driver screen (US-30)."""
from ..db import run

# One query per screen, no images: the kitchen tablet must be fast (Mateo: the old plugin took 10 seconds).
KITCHEN_DAY_QUERY = """
MATCH (o:Order {status: 'in_preparation', event_date: date($day)})-[:FOR_EVENT]->(e:EventType)
OPTIONAL MATCH (s:Staff)-[seen:CONFIRMED_ALLERGIES]->(o)
RETURN o {.id, .event_time, .guests, .delivery_notes,
    event_type: e {.name_no, .name_en},
    lines: COLLECT {
        MATCH (o)-[line:CONTAINS]->(f:FoodItem)
        RETURN {id: f.id, name_no: f.name_no, name_en: f.name_en, quantity: line.quantity} ORDER BY f.name_no
    },
    groups: COLLECT {
        MATCH (o)-[:HAS_GROUP]->(g:GuestGroup)
        RETURN {count: g.count,
                allergens: COLLECT { MATCH (g)-[:HAS_ALLERGY]->(a:Allergen) RETURN a {.code, .name_no, .name_en} },
                diets: COLLECT { MATCH (g)-[:NEEDS_DIET]->(d:Diet) RETURN d {.code, .name_no, .name_en} }}
        ORDER BY g.position
    },
    seen: CASE WHEN seen IS NULL THEN null ELSE {by: s.name, at: seen.at} END
} AS order
ORDER BY o.event_time, o.created_at
"""

# Pressing "Seen" twice (or two cooks at once) keeps the first confirmation.
CONFIRM_ALLERGIES_QUERY = """
MATCH (o:Order {id: $order_id}) WHERE o.status IN ['approved', 'in_preparation']
MATCH (s:Staff {email: $staff_email})
OPTIONAL MATCH (:Staff)-[existing:CONFIRMED_ALLERGIES]->(o)
WITH o, s, existing
FOREACH (_ IN CASE WHEN existing IS NULL THEN [1] ELSE [] END |
    CREATE (s)-[:CONFIRMED_ALLERGIES {at: datetime()}]->(o))
RETURN o.id AS id
"""

ALLERGIES_SEEN_QUERY = """
MATCH (s:Staff)-[seen:CONFIRMED_ALLERGIES]->(:Order {id: $order_id})
RETURN {by: s.name, at: seen.at} AS seen
"""

# Ingredient amounts per day, dishes ordered without a recipe (so the list never looks complete when it isn't), and
# orders not approved yet. Recipes are read now, not copied onto the order: the prep list is for buying and cooking.
PREP_LIST_QUERY = """
RETURN COLLECT {
    MATCH (o:Order)-[line:CONTAINS]->(:FoodItem)-[use:USES]->(i:Ingredient)
    WHERE o.status IN $statuses AND o.event_date >= date($first) AND o.event_date <= date($last)
    WITH i, o.event_date AS day, sum(line.quantity * use.per_portion) AS amount
    RETURN {id: i.id, name_no: i.name_no, name_en: i.name_en, unit: i.unit, day: toString(day), amount: amount}
} AS amounts,
COLLECT {
    MATCH (o:Order)-[line:CONTAINS]->(f:FoodItem)
    WHERE o.status IN $statuses AND o.event_date >= date($first) AND o.event_date <= date($last)
      AND NOT EXISTS { (f)-[:USES]->() }
    WITH f, sum(line.quantity) AS portions
    RETURN {name_no: f.name_no, name_en: f.name_en, portions: portions} ORDER BY f.name_no
} AS missing,
COUNT {
    MATCH (o:Order {status: 'submitted'})
    WHERE o.event_date >= date($first) AND o.event_date <= date($last)
} AS unapproved
"""

DRIVER_DAY_QUERY = """
MATCH (c:Customer)-[:PLACED]->(o:Order {event_date: date($day)})-[:FOR_EVENT]->(e:EventType)
WHERE o.status IN ['in_preparation', 'delivered']
OPTIONAL MATCH (s:Staff)-[d:DELIVERED]->(o)
RETURN o {.id, .status, .event_time, .guests, .delivery_address, .delivery_notes,
          event_type: e {.name_no, .name_en}, customer: c {.name, .phone},
          delivered: CASE WHEN d IS NULL THEN null ELSE {by: s.name, at: d.at} END} AS order
ORDER BY o.status DESC, o.event_time, o.created_at
"""


def kitchen_day(day) -> list[dict]:
    return [r["order"] for r in run(KITCHEN_DAY_QUERY, day=str(day))]


def confirm_allergies(order_id: str, staff_email: str) -> bool:
    return bool(run(CONFIRM_ALLERGIES_QUERY, order_id=order_id, staff_email=staff_email))


def allergies_seen(order_id: str) -> dict | None:
    rows = run(ALLERGIES_SEEN_QUERY, order_id=order_id)
    return rows[0]["seen"] if rows else None


def prep_list(days: list, statuses) -> dict:
    """One row per ingredient with its amount on each of `days` and the total."""
    row = run(PREP_LIST_QUERY, first=str(days[0]), last=str(days[-1]), statuses=list(statuses))[0]
    columns = [str(d) for d in days]
    ingredients = {}
    for a in row["amounts"]:
        item = ingredients.setdefault(a["id"], {"name_no": a["name_no"], "name_en": a["name_en"], "unit": a["unit"],
                                                "per_day": [0.0] * len(days), "total": 0.0})
        item["per_day"][columns.index(a["day"])] += a["amount"]
        item["total"] += a["amount"]
    return {"ingredients": list(ingredients.values()), "missing": row["missing"], "unapproved": row["unapproved"]}


def driver_day(day) -> list[dict]:
    return [r["order"] for r in run(DRIVER_DAY_QUERY, day=str(day))]
