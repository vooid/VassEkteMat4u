"""Cart query against real Neo4j. Opt-in: RUN_NEO4J_TESTS=1 .venv/bin/python -m pytest tests/integration"""
import os

import pytest

from app import create_app
from app.db import run
from app.repositories.cart import event_type_with_dishes
from scripts.seed import seed

pytestmark = pytest.mark.skipif(os.getenv("RUN_NEO4J_TESTS") != "1", reason="set RUN_NEO4J_TESTS=1 to run")


@pytest.fixture
def app_ctx():
    with create_app().app_context():
        seed()
        yield


def test_only_published_dishes_on_that_event_menu(app_ctx):
    event_type, dishes = event_type_with_dishes("wedding", ["layer-cake", "fish-soup", "wedding-menu", "nope"])
    assert event_type["id"] == "wedding"
    assert {d["id"] for d in dishes} == {"layer-cake", "wedding-menu"}  # fish soup isn't on the wedding menu

    run("MATCH (f:FoodItem {id: 'layer-cake'}) SET f.published = false")
    try:
        _, dishes = event_type_with_dishes("wedding", ["layer-cake"])
        assert dishes == []
    finally:
        run("MATCH (f:FoodItem {id: 'layer-cake'}) SET f.published = true")


def test_unknown_event_type(app_ctx):
    assert event_type_with_dishes("no-such-event", ["layer-cake"]) == (None, [])
