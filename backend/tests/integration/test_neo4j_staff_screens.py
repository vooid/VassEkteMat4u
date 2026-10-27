"""PIN, question, kitchen and driver queries against real Neo4j.
Opt-in: RUN_NEO4J_TESTS=1 .venv/bin/python -m pytest tests/integration"""
import os
from datetime import timedelta

import pytest

from app import auth, create_app, orders
from app.db import run
from app.repositories import customers, kitchen, questions, staff
from app.repositories import orders as orders_repo
from scripts.seed import seed

pytestmark = pytest.mark.skipif(os.getenv("RUN_NEO4J_TESTS") != "1", reason="set RUN_NEO4J_TESTS=1 to run")
CUSTOMER = "integration-screens@example.invalid"
COOK = "integration-screens-cook@example.invalid"
ADMIN = "integration-screens-admin@example.invalid"
# A date far ahead, so no real local orders share it.
DAY = orders.today() + timedelta(days=710)
CLEANUP = """
OPTIONAL MATCH (c:Customer {email: $customer})
OPTIONAL MATCH (c)-[:PLACED]->(o:Order)
OPTIONAL MATCH (o)-[:HAS_GROUP|HAD_STATUS]->(x)
OPTIONAL MATCH (c)-[:ASKED]->(q:Question)
OPTIONAL MATCH (a:Answer)-[:ANSWERS]->(q)
OPTIONAL MATCH (s:Staff) WHERE s.email IN [$cook, $admin]
DETACH DELETE x, o, a, q, c, s
"""


@pytest.fixture
def app_ctx():
    with create_app().app_context():
        seed()
        run(CLEANUP, customer=CUSTOMER, cook=COOK, admin=ADMIN)
        customers.create(CUSTOMER, auth.hash_password("hemmelig123"), "Test", "+4799999999", "en")
        staff.create(COOK, auth.hash_password("hemmelig123"), "Cook", "kitchen")
        staff.create(ADMIN, auth.hash_password("hemmelig123"), "Admin", "admin")
        yield
        run(CLEANUP, customer=CUSTOMER, cook=COOK, admin=ADMIN)


def place(groups=()):
    details = {"event_date": DAY, "delivery_address": "Bryggen 1", "delivery_notes": "Bakdøra",
               "payment_option": "invoice"}
    return orders_repo.create(CUSTOMER, "corporate-lunch", 10, {"fish-soup": 10}, details, list(groups))["id"]


def release(order_id):
    for from_status, to_status in (("submitted", "approved"), ("approved", "in_preparation")):
        assert orders_repo.change_status(order_id, from_status, to_status, ADMIN, None)


def test_pin_login_and_lockout(app_ctx):
    assert auth.authenticate_pin(COOK, "4321") == (None, False)  # no PIN set yet
    assert staff.set_pin(COOK, auth.hash_password("4321"))
    assert [u["email"] for u in staff.pin_users(auth.PIN_ROLES) if u["email"] == COOK] == [COOK]
    assert auth.authenticate_pin(COOK, "4321")[0].role == "kitchen"

    for _ in range(auth.MAX_PIN_ATTEMPTS):
        assert auth.authenticate_pin(COOK, "0000") == (None, False)
    assert auth.authenticate_pin(COOK, "4321") == (None, True)  # blocked, even with the right PIN
    staff.set_pin(COOK, auth.hash_password("4321"))  # a new PIN lifts the block
    assert auth.authenticate_pin(COOK, "4321")[0] is not None

    staff.set_pin(ADMIN, auth.hash_password("4321"))
    assert auth.authenticate_pin(ADMIN, "4321") == (None, False)  # admins never log in with a PIN


def test_questions_and_one_answer(app_ctx):
    order_id = place()
    assert questions.ask("someone@else.invalid", order_id, "Hei?") is None
    question_id = questions.ask(CUSTOMER, order_id, "Can you deliver at 11?")
    assert [q["id"] for q in questions.unanswered() if q["order_id"] == order_id] == [question_id]
    assert questions.for_order(order_id, "someone@else.invalid") == []

    assert questions.answer("EM-999999", question_id, ADMIN, "Yes") is None  # wrong order
    result = questions.answer(order_id, question_id, ADMIN, "Yes, at 11.")
    assert result["customer"]["language"] == "en" and result["question"] == "Can you deliver at 11?"
    assert questions.answer(order_id, question_id, ADMIN, "Again") is None
    [q] = questions.for_order(order_id, CUSTOMER)
    assert q["answer"]["text"] == "Yes, at 11." and q["answer"]["by"] == "Admin"
    assert not [q for q in questions.unanswered() if q["order_id"] == order_id]


def test_kitchen_day_and_allergies_seen(app_ctx):
    order_id = place([{"position": 1, "count": 2, "allergens": ["gluten"], "diets": ["vegan"]}])
    assert kitchen.kitchen_day(DAY) == []  # not released yet
    release(order_id)
    [o] = kitchen.kitchen_day(DAY)
    assert o["lines"][0]["quantity"] == 10 and o["seen"] is None
    assert o["groups"][0]["allergens"][0]["code"] == "gluten" and o["groups"][0]["diets"][0]["code"] == "vegan"

    assert kitchen.confirm_allergies(order_id, COOK)
    assert kitchen.confirm_allergies(order_id, ADMIN)  # second press keeps the first confirmation
    assert kitchen.allergies_seen(order_id)["by"] == "Cook"
    assert kitchen.kitchen_day(DAY)[0]["seen"]["by"] == "Cook"


def test_driver_day_and_delivery(app_ctx):
    order_id = place()
    release(order_id)
    [o] = kitchen.driver_day(DAY)
    assert o["customer"] == {"name": "Test", "phone": "+4799999999"} and o["delivered"] is None
    assert orders_repo.change_status(order_id, "in_preparation", "delivered", COOK, None)
    assert not orders_repo.change_status(order_id, "in_preparation", "delivered", COOK, None)
    [o] = kitchen.driver_day(DAY)
    assert o["status"] == "delivered" and o["delivered"]["by"] == "Cook"
    assert kitchen.kitchen_day(DAY) == []
