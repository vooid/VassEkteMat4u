"""Cypher queries for the cart (US-05, US-06)."""
from ..db import run


def event_type_with_dishes(event_type_id: str, dish_ids: list[str]) -> tuple[dict | None, list[dict]]:
    """The event type and those of `dish_ids` that are published and on its menu."""
    rows = run(
        """
        MATCH (e:EventType {id: $event_type_id})
        OPTIONAL MATCH (e)<-[:SUITS]-(f:FoodItem {published: true}) WHERE f.id IN $dish_ids
        RETURN e {.*} AS event_type,
               collect(f {.id, .name_no, .name_en, .price_nok, .min_order_qty}) AS dishes
        """,
        event_type_id=event_type_id, dish_ids=dish_ids,
    )
    if not rows:
        return None, []
    return rows[0]["event_type"], rows[0]["dishes"]
