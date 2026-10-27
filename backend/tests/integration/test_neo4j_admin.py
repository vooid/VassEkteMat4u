"""Admin order and staff queries against real Neo4j. Opt-in: RUN_NEO4J_TESTS=1 .venv/bin/python -m pytest tests/integration"""
import os
from datetime import timedelta

import pytest

from app import auth, create_app, orders
from app.db import run
from app.repositories import customers, staff
from app.repositories import orders as orders_repo
from scripts.seed import seed

pytestmark = pytest.mark.skipif(os.getenv("RUN_NEO4J_TESTS") != "1", reason="set RUN_NEO4J_TESTS=1 to run")
CUSTOMER = "integration-admin@example.invalid"
ADMIN = "integration-admin-staff@example.invalid"
# A date far ahead, so no real local orders share it.
DAY = orders.today() + timedelta(days=700)
CLEANUP = """
OPTIONAL MATCH (c:Customer {email: $customer})
OPTIONAL MATCH (c)-[:PLACED]->(o:Order)
OPTIONAL MATCH (o)-[:HAS_GROUP|HAD_STATUS]->(x)
OPTIONAL MATCH (s:Staff {email: $admin})
DETACH DELETE x, o, c, s
"""


@pytest.fixture
def app_ctx():
    with create_app().app_context():
        seed()
        run(CLEANUP, customer=CUSTOMER, admin=ADMIN)
        customers.create(CUSTOMER, auth.hash_password("hemmelig123"), "Test", "", "en")
        staff.create(ADMIN, auth.hash_password("hemmelig123"), "Admin", "admin")
        yield
        run(CLEANUP, customer=CUSTOMER, admin=ADMIN)


def place(guests=40, event_type="conference", dish="lentil-stew", days=700):
    details = {"event_date": orders.today() + timedelta(days=days), "event_time": "12:00",
               "delivery_address": "Bryggen 1",
               "delivery_notes": "", "payment_option": "invoice"}
    return orders_repo.create(CUSTOMER, event_type, guests, {dish: guests}, details, [])["id"]


def test_staff_accounts(app_ctx):
    assert staff.get(ADMIN) == {"email": ADMIN, "name": "Admin", "role": "admin"}
    assert staff.create(ADMIN, "x", "Again", "admin") is None
    assert auth.authenticate_staff(ADMIN, "hemmelig123").role == "admin"
    assert auth.authenticate(ADMIN, "hemmelig123") is None  # a staff account isn't a customer account


def test_list_filters_and_capacity(app_ctx):
    first, second = place(40), place(45)
    rows = orders_repo.admin_list(["submitted"], DAY.isoformat(), DAY.isoformat(), orders.BOOKED_STATUSES)
    assert {r["id"] for r in rows} == {first, second}
    assert rows[0]["customer"] == {"name": "Test", "email": CUSTOMER} and rows[0]["booked_that_day"] == 0

    assert orders_repo.change_status(first, "submitted", "approved", ADMIN, None)
    rows = orders_repo.admin_list(["approved"], DAY.isoformat(), None, orders.BOOKED_STATUSES)
    assert [r["id"] for r in rows] == [first] and rows[0]["booked_that_day"] == 40
    assert orders_repo.booked_on(DAY, second, orders.BOOKED_STATUSES, orders.WEDDING) == (40, False)
    assert orders_repo.booked_on(DAY, first, orders.BOOKED_STATUSES, orders.WEDDING) == (0, False)


def test_status_changes_are_recorded_and_guarded(app_ctx):
    order_id = place()
    assert orders_repo.change_status(order_id, "submitted", "rejected", ADMIN, "Fullbooket")
    assert not orders_repo.change_status(order_id, "submitted", "approved", ADMIN, None)  # status moved on
    order, customer = orders_repo.admin_get(order_id)
    assert customer["language"] == "en" and order["status"] == "rejected"
    last = order["history"][-1]
    assert (last["from_status"], last["to_status"], last["by_id"], last["reason"]) == \
        ("submitted", "rejected", ADMIN, "Fullbooket")


def test_delivery_and_payment(app_ctx):
    order_id = place(days=700)
    for from_status, to_status in (("submitted", "approved"), ("approved", "in_preparation"),
                                   ("in_preparation", "delivered")):
        assert orders_repo.change_status(order_id, from_status, to_status, ADMIN, None)
    assert run("MATCH (:Staff {email: $admin})-[d:DELIVERED]->(:Order {id: $id}) RETURN count(d) AS n",
               admin=ADMIN, id=order_id)[0]["n"] == 1
    assert orders_repo.change_payment(order_id, "not_paid", "invoiced", ADMIN)
    assert not orders_repo.change_payment(order_id, "not_paid", "paid", ADMIN)
    assert orders_repo.admin_get(order_id)[0]["payment_status"] == "invoiced"
