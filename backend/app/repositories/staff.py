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


# --- PIN login for kitchen and driver staff (US-27) ---

def pin_users(roles: tuple[str, ...]) -> list[dict]:
    """Staff who can log in with a PIN: right role and a PIN set. Names only, for the tablet's pick list."""
    return [r["s"] for r in run(
        "MATCH (s:Staff) WHERE s.role IN $roles AND s.pin_hash IS NOT NULL "
        "RETURN s {.email, .name, .role} AS s ORDER BY s.name", roles=list(roles))]


def get_with_pin(email: str, roles: tuple[str, ...]) -> dict | None:
    """Only for checking a PIN; never pass the result to a template."""
    rows = run(
        "MATCH (s:Staff {email: $email}) WHERE s.role IN $roles AND s.pin_hash IS NOT NULL "
        "RETURN s {.email, .name, .role, .pin_hash, .failed_pin_attempts, "
        "locked: coalesce(s.pin_locked_until > datetime(), false)} AS s",
        email=email, roles=list(roles))
    return rows[0]["s"] if rows else None


def set_pin(email: str, pin_hash: str) -> bool:
    rows = run("MATCH (s:Staff {email: $email}) SET s.pin_hash = $hash, s.failed_pin_attempts = 0, "
               "s.pin_locked_until = null RETURN s.email AS email", email=email, hash=pin_hash)
    return bool(rows)


def pin_failed(email: str, max_attempts: int, lock_minutes: int) -> None:
    """Count a wrong PIN; after `max_attempts` in a row, block PIN login for `lock_minutes`."""
    run(
        """
        MATCH (s:Staff {email: $email})
        SET s.failed_pin_attempts = coalesce(s.failed_pin_attempts, 0) + 1
        WITH s WHERE s.failed_pin_attempts >= $max
        SET s.pin_locked_until = datetime() + duration({minutes: $minutes}), s.failed_pin_attempts = 0
        """,
        email=email, max=max_attempts, minutes=lock_minutes)


def pin_succeeded(email: str) -> None:
    run("MATCH (s:Staff {email: $email}) SET s.failed_pin_attempts = 0", email=email)
