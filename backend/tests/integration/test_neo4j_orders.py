"""Order queries against real Neo4j. Opt-in: RUN_NEO4J_TESTS=1 .venv/bin/python -m pytest tests/integration"""
import os
from datetime import timedelta

import pytest

from app import auth, create_app, orders
from app.db import run
from app.repositories import customers
from app.repositories import orders as orders_repo
from scripts.seed import seed

pytestmark = pytest.mark.skipif(os.getenv("RUN_NEO4J_TESTS") != "1", reason="set RUN_NEO4J_TESTS=1 to run")
EMAIL = "integration-orders@example.invalid"
CLEANUP = """
MATCH (c:Customer {email: $email})
OPTIONAL MATCH (c)-[:PLACED]->(o:Order)
OPTIONAL MATCH (o)-[:HAS_GROUP|HAD_STATUS]->(x)
DETACH DELETE x, o, c
"""


@pytest.fixture
def app_ctx():
    with create_app().app_context():
        seed()
        run(CLEANUP, email=EMAIL)
        customers.create(EMAIL, auth.hash_password("hemmelig123"), "Test", "", "no")
        yield
        run(CLEANUP, email=EMAIL)


def details(days=30):
    return {"event_date": orders.today() + timedelta(days=days), "delivery_address": "Bryggen 1",
            "delivery_notes": "", "payment_option": "invoice"}


def lunch_minimum():
    return run("MATCH (e:EventType {id: 'corporate-lunch'}) RETURN e.min_guests AS n")[0]["n"]


def test_create_and_read_back(app_ctx):
    n = max(lunch_minimum(), 10)  # fish-soup has min_order_qty 10
    groups = [{"position": 1, "count": 2, "allergens": ["gluten", "fish"], "diets": []},
              {"position": 2, "count": 1, "allergens": [], "diets": ["vegan"]}]
    created = orders_repo.create(EMAIL, "corporate-lunch", n, {"fish-soup": n}, details(), groups)
    assert created["id"].startswith("EM-") and created["total_nok"] == n * 189

    listed = orders_repo.list_for_customer(EMAIL)
    assert [o["id"] for o in listed] == [created["id"]]
    assert listed[0]["status"] == "submitted" and listed[0]["payment_status"] == "not_paid"

    order = orders_repo.get_for_customer(EMAIL, created["id"])
    assert order["min_guests_at_order"] == lunch_minimum()
    line = order["lines"][0]
    assert (line["id"], line["quantity"], line["unit_price_nok"], line["line_total"]) == \
        ("fish-soup", n, 189, n * 189)
    assert [g["count"] for g in order["groups"]] == [2, 1]
    assert sorted(a["code"] for a in order["groups"][0]["allergens"]) == ["fish", "gluten"]
    assert [d["code"] for d in order["groups"][1]["diets"]] == ["vegan"]
    assert [h["to_status"] for h in order["history"]] == ["submitted"]
    assert order["event_date"].to_native() == details()["event_date"]

    assert orders_repo.get_for_customer("someone@else.invalid", created["id"]) is None


def test_create_refuses_orders_below_minimum(app_ctx):
    n = lunch_minimum()
    assert orders_repo.create(EMAIL, "corporate-lunch", n - 1, {"fish-soup": 50}, details(), []) is None
    assert orders_repo.create(EMAIL, "corporate-lunch", 50, {"fish-soup": 9}, details(), []) is None  # dish min 10
    assert orders_repo.create(EMAIL, "corporate-lunch", 50, {"wedding-menu": 50}, details(), []) is None  # not on menu
    assert orders_repo.list_for_customer(EMAIL) == []


def test_options_lists_seeded_allergens_and_diets(app_ctx):
    allergens, diets = orders_repo.options()
    assert {"fish", "gluten", "milk"} <= {a["code"] for a in allergens}
    assert {"vegan", "vegetarian"} <= {d["code"] for d in diets}
