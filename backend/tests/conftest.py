import pytest
from neo4j.exceptions import ServiceUnavailable

from app import create_app


class FakeRecord:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data


class FakeDriver:
    """Stands in for the Neo4j driver: records queries, returns canned rows."""

    def __init__(self):
        self.queries = []
        self.rows = []
        self.reachable = True
        self.handler = None  # optional: handler(query, params) -> rows, for tests that run several queries

    def execute_query(self, query, params=None, **kwargs):
        self.queries.append((query, params))
        rows = self.handler(query, params or {}) if self.handler else self.rows
        return [FakeRecord(r) for r in rows], None, None

    def verify_connectivity(self):
        if not self.reachable:
            raise ServiceUnavailable("no database")


@pytest.fixture
def driver():
    return FakeDriver()


@pytest.fixture
def client(driver):
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False, "NEO4J_DRIVER": driver})
    return app.test_client()


STAFF = {"admin": {"email": "admin@ektemat.test", "name": "Ingrid", "role": "admin"},
         "kitchen": {"email": "kjokken@ektemat.test", "name": "Mateo", "role": "kitchen"},
         "driver": {"email": "sjafor@ektemat.test", "name": "Ola", "role": "driver"}}


def log_in_staff(client, driver, role="admin", fallback=None):
    """Log the test client in as staff. Staff lookups are answered here; other queries go to `fallback`
    (a handler) or to driver.rows."""
    member = STAFF[role]

    def handler(query, params):
        if "MATCH (s:Staff {email: $email}) RETURN" in query:
            return [{"s": member}] if params.get("email") == member["email"] else []
        return fallback(query, params) if fallback else driver.rows
    driver.handler = handler
    with client.session_transaction() as s:
        s["_user_id"] = f"staff:{member['email']}"
        s["_fresh"] = True
    return member
