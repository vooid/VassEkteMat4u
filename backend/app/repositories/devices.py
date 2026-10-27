"""Cypher queries for devices approved for PIN login: the kitchen tablet and the drivers' phones.

The device keeps a random token in a cookie; only its SHA-256 hash is stored, so a copy of the database can't be used
to approve another device.
"""
from ..db import run

APPROVE_QUERY = """
MATCH (s:Staff {email: $staff_email})
CREATE (s)-[:APPROVED_DEVICE]->(d:PinDevice {id: randomUUID(), name: $name, token_hash: $token_hash,
                                              created_at: datetime()})
RETURN d.id AS id
"""

# Marks the device as used, so the admin can see which devices are still in use.
CHECK_QUERY = """
MATCH (d:PinDevice {token_hash: $token_hash})
SET d.last_used_at = CASE WHEN $touch THEN datetime() ELSE d.last_used_at END
RETURN d {.id, .name} AS device
"""

LIST_QUERY = """
MATCH (d:PinDevice)
OPTIONAL MATCH (s:Staff)-[:APPROVED_DEVICE]->(d)
RETURN d {.id, .name, .created_at, .last_used_at, approved_by: s.name} AS device
ORDER BY d.created_at DESC
"""


def approve(name: str, token_hash: str, staff_email: str) -> str | None:
    rows = run(APPROVE_QUERY, name=name, token_hash=token_hash, staff_email=staff_email)
    return rows[0]["id"] if rows else None


def find(token_hash: str, touch: bool = False) -> dict | None:
    rows = run(CHECK_QUERY, token_hash=token_hash, touch=touch)
    return rows[0]["device"] if rows else None


def list_all() -> list[dict]:
    return [r["device"] for r in run(LIST_QUERY)]


def revoke(device_id: str) -> bool:
    return bool(run("MATCH (d:PinDevice {id: $id}) DETACH DELETE d RETURN 1 AS done", id=device_id))
