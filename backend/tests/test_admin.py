from datetime import date, timedelta

import pytest

from app import create_app, orders
from app.repositories import orders as orders_repo
from tests.conftest import STAFF, FakeDriver, log_in_staff

TODAY = date(2026, 11, 2)
WEDDING = {"id": "wedding", "name_no": "Bryllup", "name_en": "Wedding"}
LUNCH = {"id": "corporate-lunch", "name_no": "Firmalunsj", "name_en": "Corporate lunch"}
CUSTOMER = {"email": "kari@example.no", "name": "Kari", "phone": "", "language": "en"}


def make_order(status="submitted", days=30, guests=60, event_type=WEDDING, payment="not_paid", on=None):
    return {"id": "EM-000001", "status": status, "payment_status": payment, "payment_option": "invoice",
            "event_date": (on or orders.today()) + timedelta(days=days), "guests": guests,
            "min_guests_at_order": 50, "total_nok": 41700, "event_type": event_type,
            "delivery_address": "Bryggen 1", "delivery_notes": "", "lines": [], "groups": [], "history": []}


# --- rules (US-22 – US-25) ---------------------------------------------------------

@pytest.mark.parametrize("status,days,expected", [
    ("submitted", 30, ("approved", "rejected")),
    ("approved", 6, ()),  # not locked yet
    ("approved", 5, ("in_preparation",)),
    ("in_preparation", 0, ("delivered",)),
    ("delivered", 0, ()),
    ("rejected", 30, ()),
    ("awaiting_company_approval", 30, ()),  # the company approver's decision, not Ekte Mat's
])
def test_admin_actions(status, days, expected):
    assert orders.admin_actions(make_order(status, days, on=TODAY), on=TODAY) == expected


def test_status_change_errors():
    order = make_order("submitted", on=TODAY)
    assert orders.status_change_error(order, "approved", "", on=TODAY) is None
    assert orders.status_change_error(order, "rejected", "", on=TODAY) == "reason_required"
    assert orders.status_change_error(order, "rejected", "Fullbooket", on=TODAY) is None
    assert orders.status_change_error(order, "rejected", "x" * 501, on=TODAY) == "reason_too_long"
    assert orders.status_change_error(order, "delivered", "", on=TODAY) == "change_not_allowed"


@pytest.mark.parametrize("booked,wedding_booked,event_type,guests,limit,over", [
    (300, False, LUNCH, 100, 400, False),
    (300, False, LUNCH, 101, 400, True),
    (200, False, WEDDING, 60, 250, True),  # this order is a wedding
    (200, True, LUNCH, 50, 250, False),  # a wedding is already booked
])
def test_capacity(booked, wedding_booked, event_type, guests, limit, over):
    result = orders.capacity(booked, wedding_booked, make_order(event_type=event_type, guests=guests))
    assert (result["limit"], result["over"], result["total"]) == (limit, over, booked + guests)


# --- fake database ------------------------------------------------------------

class AdminStore:
    """Fake Neo4j for the admin pages: one order, its customer, status/payment changes and the outbox."""

    def __init__(self):
        self.order = make_order()
        self.status_changes = []
        self.payment_changes = []
        self.outbox = []
        self.booked = (0, False)
        self.lose_race = False
        self.listed = None
        self.minimums = {"wedding": 50}

    def __call__(self, query, params):
        if query == orders_repo.ADMIN_LIST_QUERY:
            self.listed = params
            return [{"order": {**self.order, "customer": CUSTOMER, "booked_that_day": 120}}]
        if query == orders_repo.ADMIN_DETAIL_QUERY:
            return [{"order": self.order, "customer": CUSTOMER}] if params["order_id"] == self.order["id"] else []
        if query == orders_repo.CAPACITY_QUERY:
            return [{"guests": self.booked[0], "wedding": self.booked[1]}]
        if query == orders_repo.CHANGE_STATUS_QUERY:
            if self.lose_race:
                return []
            self.status_changes.append(params)
            self.order = {**self.order, "status": params["to_status"]}
            return [{"id": params["order_id"]}]
        if query == orders_repo.CHANGE_PAYMENT_QUERY:
            self.payment_changes.append(params)
            return [{"id": params["order_id"]}]
        if "CREATE (:OutboxMessage" in query:
            self.outbox.append(params)
            return []
        if "SET e.min_guests" in query:
            if params["id"] not in self.minimums:
                return []
            self.minimums[params["id"]] = params["min"]
            return [{"e": {"id": params["id"], "min_guests": params["min"]}}]
        if "MATCH (e:EventType)" in query:
            return [{"e": {**WEDDING, "min_guests": self.minimums["wedding"]}}]
        return []


@pytest.fixture
def store(client, driver):
    store = AdminStore()
    log_in_staff(client, driver, fallback=store)
    return store


def flashes(client):
    with client.session_transaction() as s:
        return [message for _, message in s.get("_flashes", [])]


# --- access ----------------------------------------------------------------

def test_admin_pages_need_staff_login(client, driver):
    res = client.get("/admin/orders?status=submitted")
    assert res.status_code == 302
    assert res.headers["Location"] == "/staff/login?next=/admin/orders?status%3Dsubmitted"


def test_customers_and_kitchen_staff_get_403(client, driver):
    with client.session_transaction() as s:
        s["_user_id"] = "customer:kari@example.no"
    driver.handler = lambda q, p: [{"c": CUSTOMER}] if "MATCH (c:Customer" in q else []
    assert client.get("/admin/orders").status_code == 403
    log_in_staff(client, driver, "kitchen")
    assert client.get("/admin/orders").status_code == 403
    assert client.post("/admin/orders/EM-000001/status", data={"to": "approved"}).status_code == 403


def test_staff_cannot_use_customer_pages(client, store):
    assert client.get("/orders").status_code == 403
    assert client.get("/order").status_code == 403


# --- staff login ---------------------------------------------------------------

@pytest.fixture
def staff_accounts(driver):
    from app.auth import hash_password
    member = {**STAFF["admin"], "password_hash": hash_password("riktig-passord")}

    def handler(query, params):
        if "MATCH (s:Staff" in query and params.get("email") == member["email"]:
            return [{"s": member}]
        if "MATCH (c:Customer" in query and params.get("email") == "kari@example.no":
            return [{"c": {**CUSTOMER, "password_hash": hash_password("riktig-passord")}}]
        return []
    driver.handler = handler


def test_staff_login(client, staff_accounts):
    with client.session_transaction() as s:
        s["cart"] = {"event_type": "wedding", "guests": 60, "items": {"layer-cake": 60}}
    res = client.post("/staff/login", data={"email": "Admin@Ektemat.test", "password": "riktig-passord"})
    assert res.status_code == 302 and res.headers["Location"] == "/admin/orders"
    with client.session_transaction() as s:
        assert s["_user_id"] == "staff:admin@ektemat.test" and "cart" not in s


@pytest.mark.parametrize("email", ["admin@ektemat.test", "kari@example.no"])  # wrong password; customer account
def test_staff_login_failure(client, staff_accounts, email):
    password = "feil-passord" if email.startswith("admin") else "riktig-passord"
    res = client.post("/staff/login", data={"email": email, "password": password})
    assert res.status_code == 401 and "Feil e-post eller passord." in res.get_data(as_text=True)


# --- order list (US-21) -----------------------------------------------------------

def test_order_list_defaults_to_orders_that_need_attention(client, store):
    html = client.get("/admin/orders").get_data(as_text=True)
    assert store.listed["statuses"] == ["submitted", "approved", "in_preparation"]
    assert store.listed["date_from"] is None and store.listed["booked_statuses"] == ["approved", "in_preparation"]
    assert "EM-000001" in html and "Kari" in html and "kari@example.no" in html and ">120<" in html


def test_order_list_filters(client, store):
    client.get("/admin/orders?status=delivered&status=bogus&from=2026-12-01&to=31.12.2026")
    assert store.listed["statuses"] == ["delivered"]
    assert (store.listed["date_from"], store.listed["date_to"]) == ("2026-12-01", None)


# --- order page and status changes (US-22 – US-25) ---------------------------------------

def test_order_page_for_submitted_order(client, store):
    html = client.get("/admin/orders/EM-000001").get_data(as_text=True)
    assert 'value="approved"' in html and 'value="rejected"' in html and 'value="in_preparation"' not in html
    assert "Andre godkjente bestillinger denne dagen: 0 gjester. Med denne: 60 av 250." in html
    assert client.get("/admin/orders/EM-999999").status_code == 404


def test_capacity_warning(client, store):
    store.booked = (200, False)
    html = client.get("/admin/orders/EM-000001").get_data(as_text=True)
    assert "Kapasitet: med denne bestillingen blir det 260 gjester denne dagen, over grensen på 250." in html


def test_approve_emails_customer_in_their_language(client, store):
    res = client.post("/admin/orders/EM-000001/status", data={"to": "approved"})
    assert res.headers["Location"] == "/admin/orders/EM-000001"
    change = store.status_changes[0]
    assert (change["from_status"], change["to_status"], change["staff_email"]) == \
        ("submitted", "approved", "admin@ektemat.test")
    mail = store.outbox[0]
    assert mail["recipient"] == "kari@example.no" and mail["subject"] == "Ekte Mat: order EM-000001 approved"
    assert "Wedding" in mail["body"] and "/orders/EM-000001" in mail["body"]
    assert flashes(client) == ["Status er endret til «Godkjent»."]


def test_reject_needs_a_reason_that_is_sent_to_the_customer(client, store):
    client.post("/admin/orders/EM-000001/status", data={"to": "rejected", "reason": "  "})
    assert store.status_changes == [] and store.outbox == []
    client.post("/admin/orders/EM-000001/status", data={"to": "rejected", "reason": "Fullbooket den dagen"})
    assert store.status_changes[0]["reason"] == "Fullbooket den dagen"
    assert "Reason: Fullbooket den dagen" in store.outbox[0]["body"]


def test_release_to_kitchen_only_when_locked(client, store):
    store.order = make_order("approved", days=10)
    client.post("/admin/orders/EM-000001/status", data={"to": "in_preparation"})
    assert store.status_changes == [] and flashes(client) == ["Denne endringen er ikke tillatt nå."]
    store.order = make_order("approved", days=3)
    client.post("/admin/orders/EM-000001/status", data={"to": "in_preparation"})
    assert store.status_changes[0]["to_status"] == "in_preparation"
    assert store.outbox == []  # the customer is only e-mailed on approve/reject


def test_status_change_lost_to_another_admin(client, store):
    store.lose_race = True
    client.post("/admin/orders/EM-000001/status", data={"to": "approved"})
    assert store.outbox == [] and "Noen andre endret bestillingen" in flashes(client)[0]


def test_payment_status(client, store):
    client.post("/admin/orders/EM-000001/payment", data={"to": "paid"})
    assert store.payment_changes[0]["from_status"] == "not_paid"
    store.order = make_order(payment="paid")
    client.post("/admin/orders/EM-000001/payment", data={"to": "invoiced"})
    store.order = make_order("rejected")
    client.post("/admin/orders/EM-000001/payment", data={"to": "paid"})
    assert len(store.payment_changes) == 1
    assert 'name="to" value="paid"' not in client.get("/admin/orders/EM-000001").get_data(as_text=True)


def test_status_change_needs_csrf_token(driver):
    app = create_app({"TESTING": True, "NEO4J_DRIVER": driver})
    client = app.test_client()
    store = AdminStore()
    log_in_staff(client, driver, fallback=store)
    assert client.post("/admin/orders/EM-000001/status", data={"to": "approved"}).status_code == 400
    assert client.put("/api/event-types/wedding/minimum", json={"min_guests": 60}).status_code == 400
    assert store.status_changes == []


# --- event types (US-20) -----------------------------------------------------------

def test_event_type_minimums(client, store):
    assert 'value="50"' in client.get("/admin/event-types").get_data(as_text=True)
    client.post("/admin/event-types/wedding/minimum", data={"min_guests": "60"})
    assert store.minimums["wedding"] == 60
    client.post("/admin/event-types/wedding/minimum", data={"min_guests": "266"})
    assert store.minimums["wedding"] == 60 and "fra 1 til 265" in flashes(client)[-1]
    assert client.post("/admin/event-types/nope/minimum", data={"min_guests": "10"}).status_code == 404


# --- flask create-staff ------------------------------------------------------------

def test_create_staff_command():
    created = {}

    def handler(query, params):
        if "CREATE (s:Staff" in query:
            if params["email"] in created:
                from neo4j.exceptions import ConstraintError
                raise ConstraintError("exists")
            created[params["email"]] = params
            return [{"s": {"email": params["email"], "name": params["name"], "role": params["role"]}}]
        return []
    driver = FakeDriver()
    driver.handler = handler
    runner = create_app({"TESTING": True, "NEO4J_DRIVER": driver}).test_cli_runner()

    args = ["create-staff", "Ingrid@EkteMat.no", "--name", "Ingrid Solheim"]
    result = runner.invoke(args=args, input="langt-passord\nlangt-passord\n")
    assert result.exit_code == 0 and "Created admin account for ingrid@ektemat.no" in result.output
    saved = created["ingrid@ektemat.no"]
    assert saved["role"] == "admin" and saved["hash"] != "langt-passord"

    assert runner.invoke(args=args, input="langt-passord\nlangt-passord\n").exit_code == 1  # duplicate
    short = runner.invoke(args=["create-staff", "a@b.no", "--name", "A"], input="kort\nkort\n")
    assert short.exit_code == 1 and "8–128" in short.output
    assert runner.invoke(args=["create-staff", "a@b.no", "--name", "A", "--role", "boss"],
                         input="langt-passord\nlangt-passord\n").exit_code == 2
