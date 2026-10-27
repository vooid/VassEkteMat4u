"""Cypher queries for questions about orders (US-12) and Ekte Mat's answers (US-26)."""
from ..db import run

ASK_QUERY = """
MATCH (c:Customer {email: $email})-[:PLACED]->(o:Order {id: $order_id})
CREATE (c)-[:ASKED]->(q:Question {id: randomUUID(), text: $text, created_at: datetime()})-[:ABOUT]->(o)
RETURN q.id AS id
"""

# Questions on one order, oldest first, with the answer if there is one. Used on both the customer's and the
# admin's order page; `email` is null for the admin (any order), the customer's e-mail otherwise.
FOR_ORDER_QUERY = """
MATCH (c:Customer)-[:ASKED]->(q:Question)-[:ABOUT]->(o:Order {id: $order_id})
WHERE $email IS NULL OR c.email = $email
OPTIONAL MATCH (a:Answer)-[:ANSWERS]->(q)
OPTIONAL MATCH (s:Staff)-[:WROTE]->(a)
RETURN q {.id, .text, .created_at,
          answer: CASE WHEN a IS NULL THEN null ELSE a {.text, .created_at, by: s.name} END} AS question
ORDER BY q.created_at
"""

UNANSWERED_QUERY = """
MATCH (c:Customer)-[:ASKED]->(q:Question)-[:ABOUT]->(o:Order)-[:FOR_EVENT]->(e:EventType)
WHERE NOT EXISTS { (:Answer)-[:ANSWERS]->(q) }
RETURN q {.id, .text, .created_at, order_id: o.id, event_date: o.event_date, status: o.status,
          event_type: e {.name_no, .name_en}, customer: c {.name, .email}} AS question
ORDER BY q.created_at DESC
LIMIT 200
"""

# One answer per question: a second answer (two admins at once) gets no row.
ANSWER_QUERY = """
MATCH (c:Customer)-[:ASKED]->(q:Question {id: $question_id})-[:ABOUT]->(o:Order {id: $order_id})
      -[:FOR_EVENT]->(e:EventType)
WHERE NOT EXISTS { (:Answer)-[:ANSWERS]->(q) }
MATCH (s:Staff {email: $staff_email})
CREATE (s)-[:WROTE]->(:Answer {text: $text, created_at: datetime()})-[:ANSWERS]->(q)
RETURN o {.id, .event_date, event_type: e {.name_no, .name_en}} AS order, q.text AS question,
       c {.email, .name, .language} AS customer
"""


def ask(email: str, order_id: str, text: str) -> str | None:
    rows = run(ASK_QUERY, email=email, order_id=order_id, text=text)
    return rows[0]["id"] if rows else None


def for_order(order_id: str, email: str | None = None) -> list[dict]:
    return [r["question"] for r in run(FOR_ORDER_QUERY, order_id=order_id, email=email)]


def unanswered() -> list[dict]:
    return [r["question"] for r in run(UNANSWERED_QUERY)]


def answer(order_id: str, question_id: str, staff_email: str, text: str) -> dict | None:
    """Save the answer. Returns {order, customer, question} for the e-mail, or None if already answered or unknown."""
    rows = run(ANSWER_QUERY, order_id=order_id, question_id=question_id, staff_email=staff_email, text=text)
    return rows[0] if rows else None
