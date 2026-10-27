"""Cypher queries for :Customer nodes (US-04)."""
from neo4j.exceptions import ConstraintError

from ..db import run

PUBLIC_FIELDS = "c {.email, .name, .phone, .language}"


def create(email: str, password_hash: str, name: str, phone: str, language: str) -> dict | None:
    """Create a customer. Returns None if the e-mail is taken (unique constraint customer_email)."""
    try:
        rows = run(
            f"""
            CREATE (c:Customer {{email: $email, password_hash: $hash, name: $name, phone: $phone,
                                language: $language, created_at: datetime()}})
            RETURN {PUBLIC_FIELDS} AS c
            """,
            email=email, hash=password_hash, name=name, phone=phone, language=language,
        )
    except ConstraintError:
        return None
    return rows[0]["c"]


def get(email: str) -> dict | None:
    rows = run(f"MATCH (c:Customer {{email: $email}}) WHERE c.anonymised_at IS NULL RETURN {PUBLIC_FIELDS} AS c",
               email=email)
    return rows[0]["c"] if rows else None


def get_with_hash(email: str) -> dict | None:
    """Only for checking a password at login; never pass the result to a template."""
    rows = run(
        "MATCH (c:Customer {email: $email}) WHERE c.anonymised_at IS NULL "
        "RETURN c {.email, .name, .phone, .language, .password_hash} AS c",
        email=email,
    )
    return rows[0]["c"] if rows else None


def set_language(email: str, language: str) -> None:
    run("MATCH (c:Customer {email: $email}) SET c.language = $language", email=email, language=language)
