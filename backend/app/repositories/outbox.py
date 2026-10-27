"""Cypher queries for the development e-mail outbox (:OutboxMessage)."""
from ..db import run


def add(recipient: str, subject: str, body: str) -> None:
    run(
        "CREATE (:OutboxMessage {id: randomUUID(), recipient: $recipient, subject: $subject, body: $body, "
        "created_at: datetime()})",
        recipient=recipient, subject=subject, body=body,
    )


def latest(limit: int = 50) -> list[dict]:
    rows = run("MATCH (m:OutboxMessage) RETURN m {.*} AS m ORDER BY m.created_at DESC LIMIT $limit", limit=limit)
    return [r["m"] for r in rows]
