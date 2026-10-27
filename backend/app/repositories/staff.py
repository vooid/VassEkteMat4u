"""Cypher queries for :Staff nodes (Ekte Mat employees). Created with `flask create-staff`, never by self-registration."""
from neo4j.exceptions import ConstraintError

from ..db import run

PUBLIC_FIELDS = "s {.email, .name, .role}"


def create(email: str, password_hash: str, name: str, role: str) -> dict | None:
    """Create a staff account. Returns None if the e-mail is taken (unique constraint staff_email)."""
    try:
        rows = run(
            f"""
            CREATE (s:Staff {{id: randomUUID(), email: $email, password_hash: $hash, name: $name, role: $role,
                             created_at: datetime()}})
            RETURN {PUBLIC_FIELDS} AS s
            """,
            email=email, hash=password_hash, name=name, role=role,
        )
    except ConstraintError:
        return None
    return rows[0]["s"]


def get(email: str) -> dict | None:
    rows = run(f"MATCH (s:Staff {{email: $email}}) RETURN {PUBLIC_FIELDS} AS s", email=email)
    return rows[0]["s"] if rows else None


def get_with_hash(email: str) -> dict | None:
    """Only for checking a password at login; never pass the result to a template."""
    rows = run("MATCH (s:Staff {email: $email}) RETURN s {.email, .name, .role, .password_hash} AS s", email=email)
    return rows[0]["s"] if rows else None


def admin_emails() -> list[str]:
    """Who gets the admin notifications (changed and cancelled orders, the daily lock summary)."""
    return [r["email"] for r in run("MATCH (s:Staff {role: 'admin'}) RETURN s.email AS email ORDER BY s.email")]
