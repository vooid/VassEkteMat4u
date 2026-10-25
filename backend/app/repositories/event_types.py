"""Cypher queries for :EventType nodes."""
from ..db import run


def list_all() -> list[dict]:
    return [r["e"] for r in run(
        "MATCH (e:EventType) RETURN e {.*} AS e ORDER BY e.min_guests, e.id"
    )]


def set_minimum(event_type_id: str, min_guests: int) -> dict | None:
    rows = run(
        "MATCH (e:EventType {id: $id}) SET e.min_guests = $min RETURN e {.*} AS e",
        id=event_type_id, min=min_guests,
    )
    return rows[0]["e"] if rows else None
