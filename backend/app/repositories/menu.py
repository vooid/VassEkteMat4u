"""Cypher queries for the public menu (US-01)."""
from ..db import run

MENU_QUERY = """
MATCH (e:EventType)
OPTIONAL MATCH (e)<-[:SUITS]-(f:FoodItem {published: true})
WITH e, f ORDER BY f.price_nok, f.id
WITH e, collect(f {
    .id, .name_no, .name_en, .description_no, .description_en, .price_nok, .min_order_qty,
    allergens: COLLECT { MATCH (f)-[:CONTAINS_ALLERGEN]->(a:Allergen) RETURN a {.*} ORDER BY a.code },
    diets: COLLECT { MATCH (f)-[:FITS_DIET]->(d:Diet) RETURN d {.*} ORDER BY d.code },
    image: COLLECT { MATCH (f)-[:HAS_IMAGE]->(i:Image {status: 'approved'})
                     RETURN i.path ORDER BY i.uploaded_at LIMIT 1 }[0]
}) AS items
RETURN e {.*, items: items} AS event_type
ORDER BY e.min_guests, e.id
"""


def menu_by_event_type() -> list[dict]:
    """Event types with their published food items, allergens, diets and first approved image.

    Each item's `minimum` is the larger of the event type's current minimum and the item's own minimum order
    quantity (basic_desc.txt: the lower limit is drawn from the event type).
    """
    event_types = [r["event_type"] for r in run(MENU_QUERY)]
    for e in event_types:
        for item in e["items"]:
            item["minimum"] = max(e["min_guests"], item.get("min_order_qty") or 0)
    return event_types
