"""Customer queries against real Neo4j. Opt-in: RUN_NEO4J_TESTS=1 .venv/bin/python -m pytest tests/integration"""
import os

import pytest

from app import auth, create_app
from app.db import run
from app.repositories import customers
from scripts.seed import seed

pytestmark = pytest.mark.skipif(os.getenv("RUN_NEO4J_TESTS") != "1", reason="set RUN_NEO4J_TESTS=1 to run")
EMAIL = "integration-test@example.invalid"


@pytest.fixture
def app_ctx():
    with create_app().app_context():
        seed()
        run("MATCH (c:Customer {email: $email}) DETACH DELETE c", email=EMAIL)
        yield
        run("MATCH (c:Customer {email: $email}) DETACH DELETE c", email=EMAIL)


def test_create_is_unique_and_hash_is_not_public(app_ctx):
    created = customers.create(EMAIL, auth.hash_password("hemmelig123"), "Test", "", "en")
    assert created == {"email": EMAIL, "name": "Test", "phone": "", "language": "en"}
    assert customers.create(EMAIL, auth.hash_password("other-pass"), "Other", "", "no") is None
    assert "password_hash" not in customers.get(EMAIL)


def test_authenticate_and_language(app_ctx):
    customers.create(EMAIL, auth.hash_password("hemmelig123"), "Test", "", "no")
    assert auth.authenticate(EMAIL, "hemmelig123").email == EMAIL
    assert auth.authenticate(EMAIL, "wrong") is None
    customers.set_language(EMAIL, "en")
    assert customers.get(EMAIL)["language"] == "en"
