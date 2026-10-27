"""Change, cancel, reminder and lock queries against real Neo4j.
Opt-in: RUN_NEO4J_TESTS=1 .venv/bin/python -m pytest tests/integration"""
import os
from datetime import timedelta

import pytest

from app import auth, create_app, jobs, orders
from app.db import run
from app.repositories import customers
from app.repositories import orders as orders_repo
from scripts.seed import seed

pytestmark = pytest.mark.skipif(os.getenv("RUN_NEO4J_TESTS") != "1", reason="set RUN_NEO4J_TESTS=1 to run")
EMAIL = "integration-changes@example.invalid"
CLEANUP = """
MATCH (c:Customer {email: $email})
OPTIONAL MATCH (c)-[:PLACED]->(o:Order)
OPTIONAL MATCH (o)-[:HAS_GROUP|HAD_STATUS]->(x)
DETACH DELETE x, o, c
WITH 1 AS done
MATCH (m:OutboxMessage {recipient: $email}) DETACH DELETE m
"""


@pytest.fixture
def app_ctx():
    with create_app().app_context():
        seed()
        run(CLEANUP, email=EMAIL)
        customers.create(EMAIL, auth.hash_password("hemmelig123"), "Test", "", "no")
        yield
        run(CLEANUP, email=EMAIL)


def place(days, guests=10, items=None):
    details = {"event_date": orders.today() + timedelta(days=days), "event_time": "12:00",
               "delivery_address": "Bryggen 1",
               "delivery_notes": "", "payment_option": "invoice"}
    return orders_repo.create(EMAIL, "corporate-lunch", guests, items or {"fish-soup": guests}, details,
                              [{"position": 1, "count": 2, "allergens": ["gluten"], "diets": []}])["id"]


def set_status(order_id, status):
    run("MATCH (o:Order {id: $id}) SET o.status = $status", id=order_id, status=status)


def change(order_id, guests, items, groups=()):
    return orders_repo.change(EMAIL, order_id, {"guests": guests, "event_time": "18:15", "items": items,
                                                "delivery_notes": "Ny dør",
                                                "groups": list(groups)},
                              orders.CUSTOMER_CHANGEABLE, orders.lock_until())


def test_change_keeps_old_prices_and_replaces_lines_and_groups(app_ctx):
    order_id = place(30)
    run("MATCH (f:FoodItem {id: 'fish-soup'}) SET f.price_nok = 999")  # price rise after ordering
    try:
        result = change(order_id, 12, {"fish-soup": 12, "beetroot-salad": 12},
                        [{"position": 1, "count": 3, "allergens": [], "diets": ["vegan"]}])
    finally:
        run("MATCH (f:FoodItem {id: 'fish-soup'}) SET f.price_nok = 189")
    assert result["total_nok"] == 12 * 189 + 12 * 165  # fish soup at the old price, salad at today's price
    order = orders_repo.get_for_customer(EMAIL, order_id)
    assert sorted((line["id"], line["quantity"]) for line in order["lines"]) == \
        [("beetroot-salad", 12), ("fish-soup", 12)]
    assert [(g["count"], [d["code"] for d in g["diets"]], g["allergens"]) for g in order["groups"]] == \
        [(3, ["vegan"], [])]
    assert order["delivery_notes"] == "Ny dør" and order["guests"] == 12 and order["event_time"] == "18:15"
    assert run("MATCH (g:GuestGroup) WHERE NOT (g)<-[:HAS_GROUP]-() RETURN count(g) AS n")[0]["n"] == 0
    last = order["history"][-1]
    assert (last["from_status"], last["to_status"], last["by_role"]) == ("submitted", "submitted", "customer")


def test_change_refused_when_locked_or_below_saved_minimum(app_ctx):
    locked = place(30)
    run("MATCH (o:Order {id: $id}) SET o.event_date = date() + duration({days: 5})", id=locked)
    assert change(locked, 12, {"fish-soup": 12}) is None
    order_id = place(30)
    saved_min = orders_repo.get_for_customer(EMAIL, order_id)["min_guests_at_order"]
    assert change(order_id, saved_min - 1, {"fish-soup": 10}) is None
    assert change(order_id, 10, {"fish-soup": 9}) is None  # dish minimum 10
    assert change(order_id, 10, {"wedding-menu": 10}) is None  # not on this event type's menu


def test_cancel(app_ctx):
    order_id = place(30)
    set_status(order_id, "approved")
    assert orders_repo.cancel(EMAIL, order_id, orders.CUSTOMER_CHANGEABLE, orders.lock_until()) == "approved"
    assert orders_repo.get_for_customer(EMAIL, order_id)["status"] == "cancelled"
    assert orders_repo.cancel(EMAIL, order_id, orders.CUSTOMER_CHANGEABLE, orders.lock_until()) is None
    assert change(order_id, 10, {"fish-soup": 10}) is None  # cancelled is final


def test_daily_job_reminds_and_locks_once(app_ctx):
    reminded, too_late, not_approved, locked_now = place(7), place(5), place(7), place(4)
    for order_id in (reminded, too_late, locked_now):
        set_status(order_id, "approved")
    mine = {reminded, too_late, not_approved, locked_now}

    first = jobs.run_daily()
    assert mine & set(first["reminded"]) == {reminded}  # not too_late (already locked), not the submitted one
    assert mine & set(first["locked"]) == {too_late, locked_now}
    second = jobs.run_daily()
    assert not mine & set(second["reminded"]) and not mine & set(second["locked"])

    mails = run("MATCH (m:OutboxMessage {recipient: $email}) RETURN m.subject AS subject", email=EMAIL)
    assert [m["subject"] for m in mails] == [f"Ekte Mat: én uke til arrangementet ({reminded})"]
    assert run("MATCH (o:Order {id: $id}) RETURN o.locked_at IS NOT NULL AS locked", id=locked_now)[0]["locked"]
