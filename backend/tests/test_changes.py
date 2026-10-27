import re
from datetime import date, datetime, timedelta, timezone

import pytest
from werkzeug.datastructures import MultiDict

from app import create_app, jobs, orders
from app.repositories import orders as orders_repo
from app.repositories import questions
from tests.conftest import FakeDriver

TODAY = date(2026, 11, 2)
EMAIL = "kari@example.no"
LUNCH = {"id": "corporate-lunch", "name_no": "Firmalunsj", "name_en": "Corporate lunch"}
SOUP = {"id": "fish-soup", "name_no": "Fiskesuppe", "name_en": "Fish soup", "min_order_qty": 10, "price_nok": 189}
SALAD = {"id": "beetroot-salad", "name_no": "Rødbetsalat", "name_en": "Beetroot salad", "min_order_qty": 8,
         "price_nok": 165}
ALLERGENS = [{"code": "gluten", "name_no": "Gluten", "name_en": "Gluten"}]
DIETS = [{"code": "vegan", "name_no": "Vegansk", "name_en": "Vegan"}]
CODES = ({"gluten"}, {"vegan"})


def make_order(status="approved", days=30, on=None):
    return {"id": "EM-000001", "status": status, "payment_status": "not_paid", "payment_option": "invoice",
            "event_date": (on or orders.today()) + timedelta(days=days), "event_time": "12:00", "guests": 12, "min_guests_at_order": 8,
            "total_nok": 2268, "event_type": LUNCH, "delivery_address": "Bryggen 1", "delivery_notes": "Bakdøra",
            "lines": [{**SOUP, "quantity": 12, "unit_price_nok": 189, "line_total": 2268}],
            "groups": [{"position": 1, "count": 2, "allergens": ALLERGENS, "diets": []}],
            "history": [{"from_status": "submitted", "to_status": "submitted",
                         "at": datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc), "by_role": "customer"}]}


# --- rules (US-09, US-10) -------------------------------------------------------

@pytest.mark.parametrize("status,days,ok", [
    ("submitted", 6, True), ("approved", 6, True), ("approved", 5, False),
    ("in_preparation", 30, False), ("delivered", 30, False), ("cancelled", 30, False),
])
def test_customer_can_change(status, days, ok):
    assert orders.customer_can_change(make_order(status, days, on=TODAY), on=TODAY) is ok


def test_last_change_date_is_six_days_before():
    assert orders.last_change_date(date(2026, 12, 10)) == date(2026, 12, 4)
    assert orders.is_locked(date(2026, 12, 10), on=date(2026, 12, 5))
    assert not orders.is_locked(date(2026, 12, 10), on=date(2026, 12, 4))


def change_form(**overrides):
    data = {"guests": "12", "event_time": "11:30", "qty-fish-soup": "12", "qty-beetroot-salad": "", "delivery_notes": "Bakdøra"}
    data.update(overrides)
    return MultiDict(data)


def test_parse_change():
    parsed, errors = orders.parse_change(change_form(**{"qty-beetroot-salad": "10", "group-1-count": "2",
                                                        "group-1-diets": "vegan"}),
                                         make_order(), [SOUP, SALAD], *CODES)
    assert errors == []
    assert parsed == {"guests": 12, "event_time": "11:30", "items": {"fish-soup": 12, "beetroot-salad": 10}, "delivery_notes": "Bakdøra",
                      "groups": [{"position": 1, "count": 2, "allergens": [], "diets": ["vegan"]}]}


@pytest.mark.parametrize("overrides,key", [
    ({"event_time": ""}, "event_time_invalid"),
    ({"guests": "7"}, "guests_below_saved_minimum"),  # saved minimum 8
    ({"guests": ""}, "guests_missing"),
    ({"qty-fish-soup": "9"}, "dish_below_minimum"),  # the dish's own minimum is 10
    ({"qty-fish-soup": "0"}, "order_needs_a_dish"),
    ({"qty-fish-soup": "abc"}, "invalid_quantity"),
    ({"group-1-count": "13", "group-1-allergens": "gluten"}, "groups_exceed_guests"),
])
def test_parse_change_errors(overrides, key):
    errors = orders.parse_change(change_form(**overrides), make_order(), [SOUP, SALAD], *CODES)[1]
    assert key in [k for k, _ in errors]


def test_saved_minimum_applies_even_if_event_minimum_is_higher_now():
    # The admin may have raised the event type's minimum since; the order keeps min_guests_at_order (US-09).
    parsed, errors = orders.parse_change(change_form(guests="8", **{"qty-fish-soup": "10"}), make_order(),
                                         [SOUP], *CODES)
    assert errors == [] and parsed["guests"] == 8


# --- pages ---------------------------------------------------------------------

class ChangeStore:
    """Fake Neo4j for the customer's order, changes, cancellation, admins and the outbox."""

    def __init__(self):
        self.order = make_order()
        self.owner = EMAIL
        self.changes, self.cancels, self.outbox = [], [], []
        self.refuse = False

    def __call__(self, query, params):
        mine = params.get("email") == self.owner and params.get("order_id") == self.order["id"]
        if query == orders_repo.DETAIL_QUERY:
            return [{"order": self.order}] if mine else []
        if query == orders_repo.CHANGE_OPTIONS_QUERY:
            return [{"dishes": [{**SOUP, "quantity": 12}, {**SALAD, "quantity": None}]}] if mine else []
        if query == orders_repo.OPTIONS_QUERY:
            return [{"allergens": ALLERGENS, "diets": DIETS}]
        if query == orders_repo.CHANGE_QUERY:
            if self.refuse or not mine:
                return []
            self.changes.append(params)
            return [{"id": self.order["id"], "status": self.order["status"], "total_nok": 3918}]
        if query == orders_repo.CANCEL_QUERY:
            if self.refuse or not mine:
                return []
            self.cancels.append(params)
            return [{"id": self.order["id"], "from_status": self.order["status"]}]
        if "MATCH (s:Staff {role: 'admin'})" in query:
            return [{"email": "ingrid@ektemat.test"}]
        if "CREATE (:OutboxMessage" in query:
            self.outbox.append(params)
            return []
        if query == questions.FOR_ORDER_QUERY:
            return []
        if "MATCH (c:Customer" in query:
            return [{"c": {"email": EMAIL, "name": "Kari", "phone": "", "language": "no"}}] \
                if params.get("email") == EMAIL else []
        return []


@pytest.fixture
def store(client, driver):
    driver.handler = ChangeStore()
    with client.session_transaction() as s:
        s["_user_id"] = f"customer:{EMAIL}"
    return driver.handler


def test_order_page_offers_change_and_cancel_until_the_lock(client, store):
    html = client.get("/orders/EM-000001").get_data(as_text=True)
    last_day = orders.last_change_date(store.order["event_date"]).strftime("%d.%m.%Y")
    assert f"Du kan endre eller avbestille til og med {last_day}." in html
    assert "/orders/EM-000001/change" in html and "/orders/EM-000001/cancel" in html
    assert "Bakdøra" in html

    store.order = make_order(days=5)
    html = client.get("/orders/EM-000001").get_data(as_text=True)
    assert "5 dager eller mindre" in html and "/orders/EM-000001/cancel" not in html


def test_change_form_is_filled_in(client, store):
    html = client.get("/orders/EM-000001/change").get_data(as_text=True)
    assert 'name="guests"' in html and 'value="12"' in html
    assert 'name="qty-fish-soup"' in html and 'name="qty-beetroot-salad"' in html
    assert re.search(r'name="group-1-allergens" value="gluten"\s+checked', html)  # saved guest group
    assert 'name="event_time"' in html and 'value="12:00"' in html


def test_change_approved_order_saves_and_tells_admin(client, store):
    res = client.post("/orders/EM-000001/change", data={"event_time": "12:00", "guests": "14", "qty-fish-soup": "14",
                                                        "qty-beetroot-salad": "8", "delivery_notes": "Ny dør"})
    assert res.headers["Location"] == "/orders/EM-000001"
    params = store.changes[0]
    assert params["guests"] == 14 and params["delivery_notes"] == "Ny dør" and params["event_time"] == "12:00"
    assert params["items"] == [{"dish_id": "fish-soup", "quantity": 14}, {"dish_id": "beetroot-salad", "quantity": 8}]
    assert params["lock_until"] == (orders.today() + timedelta(days=5)).isoformat()
    assert [m["recipient"] for m in store.outbox] == ["ingrid@ektemat.test"]
    assert "Godkjent bestilling EM-000001 er endret av kunden" == store.outbox[0]["subject"]
    assert "Nå: 14 gjester, 3918 kr." in store.outbox[0]["body"]


def test_change_submitted_order_does_not_e_mail_admin(client, store):
    store.order = make_order("submitted")
    client.post("/orders/EM-000001/change", data={"event_time": "12:00", "guests": "12", "qty-fish-soup": "12"})
    assert len(store.changes) == 1 and store.outbox == []


def test_invalid_change_shows_errors(client, store):
    res = client.post("/orders/EM-000001/change", data={"event_time": "12:00", "guests": "7", "qty-fish-soup": "9"})
    html = res.get_data(as_text=True)
    assert res.status_code == 400 and store.changes == []
    assert "minst 8 gjester" in html and "Fiskesuppe: minst 10 porsjoner." in html


def test_locked_order_cannot_be_changed_or_cancelled(client, store):
    store.order = make_order(days=4)
    for url, data in (("/orders/EM-000001/change", {"guests": "12", "qty-fish-soup": "12"}),
                      ("/orders/EM-000001/cancel", {"confirm": "yes"})):
        res = client.post(url, data=data)
        assert res.headers["Location"] == "/orders/EM-000001"
    assert client.get("/orders/EM-000001/change").status_code == 302
    assert store.changes == [] and store.cancels == []


def test_database_refusal_is_reported(client, store):
    store.refuse = True  # e.g. the job locked it a second ago, or a dish was removed from the menu
    client.post("/orders/EM-000001/change", data={"event_time": "12:00", "guests": "12", "qty-fish-soup": "12"})
    with client.session_transaction() as s:
        assert "kan ikke endres lenger" in s["_flashes"][-1][1]
    assert store.outbox == []


def test_cancel_needs_confirmation_and_tells_admin_and_customer(client, store):
    client.post("/orders/EM-000001/cancel", data={})
    assert store.cancels == []
    client.post("/orders/EM-000001/cancel", data={"confirm": "yes"})
    assert len(store.cancels) == 1
    recipients = sorted(m["recipient"] for m in store.outbox)
    assert recipients == ["ingrid@ektemat.test", EMAIL]
    customer_mail = next(m for m in store.outbox if m["recipient"] == EMAIL)
    assert customer_mail["subject"] == "Ekte Mat: bestilling EM-000001 er avbestilt"


def test_other_customers_order(client, store):
    store.owner = "someone@else.no"
    assert client.get("/orders/EM-000001/change").status_code == 404
    assert client.post("/orders/EM-000001/cancel", data={"confirm": "yes"}).status_code == 404


def test_history_shows_customer_changes(client, store):
    html = client.get("/orders/EM-000001").get_data(as_text=True)
    assert "Endret av kunden" in html


# --- daily job (US-11, lock) --------------------------------------------------------

class JobStore:
    def __init__(self):
        self.outbox = []
        self.params = {}

    def __call__(self, query, params):
        if query == orders_repo.REMINDER_QUERY:
            self.params["reminder"] = params
            return [{"order": {"id": "EM-000001", "event_date": date(2026, 11, 9), "guests": 40},
                     "event_type": LUNCH, "customer": {"email": EMAIL, "name": "Kari", "language": "en"}}]
        if query == orders_repo.LOCK_QUERY:
            self.params["lock"] = params
            return [{"order": {"id": "EM-000002", "status": "approved", "event_date": date(2026, 11, 7),
                               "guests": 60, "event_type": LUNCH}},
                    {"order": {"id": "EM-000003", "status": "submitted", "event_date": date(2026, 11, 7),
                               "guests": 20, "event_type": LUNCH}}]
        if "MATCH (s:Staff {role: 'admin'})" in query:
            return [{"email": "ingrid@ektemat.test"}]
        if "CREATE (:OutboxMessage" in query:
            self.outbox.append(params)
        return []


def job_app(store, **config):
    driver = FakeDriver()
    driver.handler = store
    return create_app({"TESTING": True, "NEO4J_DRIVER": driver, "SITE_URL": "https://ektemat.example", **config})


def test_daily_job_sends_reminders_and_locks():
    store = JobStore()
    with job_app(store).app_context():
        result = jobs.run_daily(TODAY)
    assert result == {"reminded": ["EM-000001"], "locked": ["EM-000002", "EM-000003"]}
    assert store.params["reminder"] == {"remind_until": "2026-11-09", "lock_until": "2026-11-07"}
    assert store.params["lock"]["lock_until"] == "2026-11-07"
    assert store.params["lock"]["changeable"] == ["submitted", "approved"]

    reminder, summary = store.outbox
    assert reminder["recipient"] == EMAIL and reminder["subject"] == "Ekte Mat: one week to your event (EM-000001)"
    assert "until and including 3 Nov 2026" in reminder["body"]
    assert "https://ektemat.example/orders/EM-000001" in reminder["body"]
    assert summary["recipient"] == "ingrid@ektemat.test"
    assert summary["subject"] == "Ekte Mat: bestillinger låst 02.11.2026 (2)"
    assert "- EM-000003: Firmalunsj, 07.11.2026, 20 gjester (Sendt inn)" in summary["body"]
    assert "Ikke godkjent ennå: EM-000003." in summary["body"]


def test_run_daily_jobs_command():
    store = JobStore()
    runner = job_app(store).test_cli_runner()
    result = runner.invoke(args=["run-daily-jobs", "--date", "2026-11-02"])
    assert result.exit_code == 0
    assert "Reminders sent: 1 EM-000001" in result.output and "Orders locked: 2 EM-000002 EM-000003" in result.output
    assert runner.invoke(args=["run-daily-jobs", "--date", "02.11.2026"]).exit_code == 2
