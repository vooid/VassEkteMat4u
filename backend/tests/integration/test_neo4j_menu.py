"""Runs the real Cypher against a local Neo4j. Opt-in, because it writes sample data:

    RUN_NEO4J_TESTS=1 .venv/bin/python -m pytest tests/integration
"""
import os

import pytest

from app import create_app
from app.db import run
from app.repositories.menu import menu_by_event_type
from scripts.seed import FOOD_ITEMS, seed

pytestmark = pytest.mark.skipif(os.getenv("RUN_NEO4J_TESTS") != "1", reason="set RUN_NEO4J_TESTS=1 to run")


@pytest.fixture
def app_ctx():
    app = create_app()
    with app.app_context():
        seed()
        yield app


def test_menu_query_against_neo4j(app_ctx):
    menu = {e["id"]: e for e in menu_by_event_type()}
    assert set(menu) >= {"corporate-lunch", "birthday", "confirmation", "christmas-party", "conference", "wedding"}
    for e in menu.values():
        assert e["items"], f"{e['id']} has no dishes"

    soup = next(i for i in menu["corporate-lunch"]["items"] if i["id"] == "fish-soup")
    assert soup["price_nok"] == 189
    assert {a["code"] for a in soup["allergens"]} == {"fish", "milk", "gluten", "celery"}
    assert soup["image"] is None


def test_unpublished_items_and_unapproved_images_are_hidden(app_ctx):
    run("MATCH (f:FoodItem {id: 'lentil-stew'}) SET f.published = false")
    run("MATCH (f:FoodItem {id: 'fish-soup'}) "
        "MERGE (f)-[:HAS_IMAGE]->(:Image {id: 'test-pending', path: '/x.jpg', status: 'pending'})")
    try:
        lunch = next(e for e in menu_by_event_type() if e["id"] == "corporate-lunch")
        ids = {i["id"] for i in lunch["items"]}
        assert "lentil-stew" not in ids
        assert next(i for i in lunch["items"] if i["id"] == "fish-soup")["image"] is None
    finally:
        run("MATCH (f:FoodItem {id: 'lentil-stew'}) SET f.published = true")
        run("MATCH (i:Image {id: 'test-pending'}) DETACH DELETE i")


def test_seed_is_repeatable(app_ctx):
    seed()
    count = run("MATCH (f:FoodItem) WHERE f.id IN $ids RETURN count(f) AS n", ids=[f[0] for f in FOOD_ITEMS])
    assert count[0]["n"] == len(FOOD_ITEMS)
    assert run("MATCH (f:FoodItem) WHERE f.just_created IS NOT NULL RETURN count(f) AS n")[0]["n"] == 0
