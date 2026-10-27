import re
from datetime import date, datetime, timedelta, timezone

import pytest
from werkzeug.datastructures import MultiDict

from app import create_app, i18n, mail, orders
from app.repositories import orders as orders_repo
from app.repositories import questions
from tests.conftest import FakeDriver

TODAY = date(2026, 11, 2)
EMAIL = "kari@example.no"
WEDDING = {"id": "wedding", "name_no": "Bryllup", "name_en": "Wedding", "min_guests": 50}
MENU3 = {"id": "wedding-menu", "name_no": "Bryllupsmeny", "name_en": "Wedding menu", "price_nok": 695,
         "min_order_qty": 40}
ALLERGENS = [{"code": "gluten", "name_no": "Gluten", "name_en": "Gluten"},
             {"code": "nuts", "name_no": "Nøtter", "name_en": "Nuts"}]
DIETS = [{"code": "vegan", "name_no": "Vegansk", "name_en": "Vegan"}]
CODES = ({"gluten", "nuts"}, {"vegan"})


def checkout_form(**overrides):
    data = {"event_date": (TODAY + timedelta(days=30)).isoformat(), "event_time": "12:00", "delivery_address": "Bryggen 1, Bergen",
            "delivery_notes": "", "payment_option": "invoice"}
    data.update(overrides)
    return MultiDict(data)


# --- rules (US-07) ---------------------------------------------------------------

def test_valid_form_without_groups():
    details, groups, errors = orders.parse_checkout(checkout_form(), 50, *CODES, on=TODAY)
    assert errors == [] and groups == []
    assert details["event_date"] == TODAY + timedelta(days=30) and details["event_time"] == "12:00"
    assert details["delivery_address"] == "Bryggen 1, Bergen"


@pytest.mark.parametrize("days,ok", [(5, False), (6, True), (730, True), (731, False)])
def test_event_date_must_be_more_than_five_days_ahead(days, ok):
    form = checkout_form(event_date=(TODAY + timedelta(days=days)).isoformat())
    errors = orders.parse_checkout(form, 50, *CODES, on=TODAY)[2]
    assert (errors == []) is ok


def test_parse_time():
    assert orders.parse_time("9:05") == "09:05" and orders.parse_time(" 23:00 ") == "23:00"
    assert orders.parse_time("24:00") is None and orders.parse_time(None) is None


@pytest.mark.parametrize("field,value,key", [
    ("event_date", "", "event_date_invalid"),
    ("event_date", "31.12.2026", "event_date_invalid"),
    ("event_time", "", "event_time_invalid"),
    ("event_time", "05:45", "event_time_invalid"),  # before opening hours
    ("event_time", "23:30", "event_time_invalid"),
    ("event_time", "12.00", "event_time_invalid"),
    ("delivery_address", "   ", "address_required"),
    ("delivery_notes", "x" * 501, "text_too_long"),
    ("payment_option", "cash", "payment_option_required"),
])
def test_invalid_details(field, value, key):
    errors = orders.parse_checkout(checkout_form(**{field: value}), 50, *CODES, on=TODAY)[2]
    assert [k for k, _ in errors] == [key]


def test_guest_groups_are_counts_with_known_codes_only():
    form = checkout_form()
    form.add("group-1-count", "4")
    form.setlist("group-1-allergens", ["gluten", "peanut-butter"])
    form.add("group-2-count", "")  # empty row: ignored
    form.add("group-3-count", "2")
    form.add("group-3-diets", "vegan")
    groups, errors = orders.parse_checkout(form, 50, *CODES, on=TODAY)[1:]
    assert errors == []
    assert groups == [{"position": 1, "count": 4, "allergens": ["gluten"], "diets": []},
                      {"position": 3, "count": 2, "allergens": [], "diets": ["vegan"]}]


def test_guest_group_errors():
    form = checkout_form()
    form.add("group-1-count", "0")
    form.add("group-1-allergens", "nuts")
    form.add("group-2-count", "3")  # nothing ticked
    form.add("group-3-count", "51")
    form.add("group-3-diets", "vegan")
    errors = orders.parse_checkout(form, 50, *CODES, on=TODAY)[2]
    assert errors == [("group_count_invalid", {"n": 1}), ("group_needs_something", {"n": 2}),
                      ("groups_exceed_guests", {"n": 50})]


def test_split_current_and_past():
    rows = [{"id": "A", "status": "delivered"}, {"id": "B", "status": "cancelled"},
            {"id": "C", "status": "submitted"}, {"id": "D", "status": "approved"}]
    current, past = orders.split_current_past(rows)
    assert [o["id"] for o in current] == ["C", "D"]
    assert [o["id"] for o in past] == ["B", "A"]  # most recent first


def test_dates_are_formatted_per_language():
    app = create_app({"TESTING": True, "NEO4J_DRIVER": FakeDriver()})
    with app.test_request_context():
        app.preprocess_request()
        assert i18n.format_date(date(2026, 12, 3)) == "03.12.2026"
        assert i18n.format_datetime(datetime(2026, 12, 3, 9, 5, tzinfo=timezone.utc)) == "03.12.2026 10:05"
        i18n.g.lang = "en"
        assert i18n.format_date(date(2026, 12, 3)) == "3 Dec 2026"


# --- pages (US-07, US-08) -----------------------------------------------------------

class OrderStore:
    """Fake Neo4j for customer, cart, order and outbox queries."""

    def __init__(self):
        self.created = []  # params of CREATE_QUERY calls
        self.outbox = []
        self.create_fails = False
        self.orders = {}  # id -> (owner e-mail, detail dict)

    def __call__(self, query, params):
        if query == orders_repo.CREATE_QUERY:
            if self.create_fails:
                return []
            self.created.append(params)
            return [{"id": params["order_id"], "total_nok": 50 * MENU3["price_nok"]}]
        if "CREATE (:OutboxMessage" in query:
            self.outbox.append(params)
            return []
        if "MATCH (m:OutboxMessage)" in query:
            return [{"m": {"recipient": p["recipient"], "subject": p["subject"], "body": p["body"],
                           "created_at": datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)}} for p in self.outbox]
        if query == orders_repo.OPTIONS_QUERY:
            return [{"allergens": ALLERGENS, "diets": DIETS}]
        if query == orders_repo.LIST_QUERY:
            return [{"order": o} for owner, o in self.orders.values() if owner == params["email"]]
        if query == orders_repo.DETAIL_QUERY:
            owner, o = self.orders.get(params["order_id"], (None, None))
            return [{"order": o}] if owner == params["email"] else []
        if "OPTIONAL MATCH (e)<-[:SUITS]" in query:
            return [{"event_type": WEDDING, "dishes": [MENU3] if "wedding-menu" in params["dish_ids"] else []}]
        if query == questions.FOR_ORDER_QUERY:
            return []
        if "MATCH (c:Customer" in query:
            return [{"c": {"email": EMAIL, "name": "Kari", "phone": "", "language": "no"}}] \
                if params.get("email") == EMAIL else []
        return []


@pytest.fixture
def store(driver):
    driver.handler = OrderStore()
    return driver.handler


def log_in(client, cart=None):
    with client.session_transaction() as s:
        s["_user_id"] = f"customer:{EMAIL}"
        s["_fresh"] = True
        if cart:
            s["cart"] = cart


GOOD_CART = {"event_type": "wedding", "guests": 50, "items": {"wedding-menu": 50}}


def future(days=30):
    return (orders.today() + timedelta(days=days)).isoformat()


def submit(client, **overrides):
    data = {"event_date": future(), "event_time": "17:30", "delivery_address": "Bryggen 1, Bergen", "delivery_notes": "Bakdøra",
            "payment_option": "vipps", "group-1-count": "4", "group-1-allergens": "gluten"}
    data.update(overrides)
    return client.post("/order", data=data)


def test_checkout_needs_login(client, store):
    res = client.get("/order")
    assert res.status_code == 302 and "/login?next=%2Forder" in res.headers["Location"]


def test_checkout_needs_a_cart_that_meets_the_minimums(client, store):
    log_in(client, {**GOOD_CART, "guests": 49})
    res = client.get("/order")
    assert res.status_code == 302 and res.headers["Location"].endswith("/cart")


def test_checkout_page(client, store):
    log_in(client, GOOD_CART)
    html = client.get("/order").get_data(as_text=True)
    assert f'min="{orders.earliest_event_date().isoformat()}"' in html
    assert 'name="group-1-allergens" value="gluten"' in html
    assert "34750 kr" in html  # 50 × 695


def test_invalid_checkout_keeps_the_values(client, store):
    log_in(client, GOOD_CART)
    res = submit(client, event_date=future(2), delivery_address="")
    html = res.get_data(as_text=True)
    assert res.status_code == 400
    assert "Arrangementet må være mer enn 5 dager fram i tid" in html
    assert "Bakdøra" in html and re.search(r'value="gluten"\s+checked', html)
    assert store.created == []


def test_submit_creates_order_empties_cart_and_sends_confirmation(client, store):
    log_in(client, GOOD_CART)
    res = submit(client)
    order_id = store.created[0]["order_id"]
    assert res.status_code == 302 and res.headers["Location"] == f"/orders/{order_id}"
    params = store.created[0]
    assert params["email"] == EMAIL and params["guests"] == 50
    assert params["items"] == [{"dish_id": "wedding-menu", "quantity": 50}]
    assert params["groups"] == [{"position": 1, "count": 4, "allergens": ["gluten"], "diets": []}]
    assert params["event_date"] == future() and params["payment_option"] == "vipps"
    assert params["event_time"] == "17:30"
    with client.session_transaction() as s:
        assert "cart" not in s
    assert len(store.outbox) == 1
    mail_sent = store.outbox[0]
    assert mail_sent["recipient"] == EMAIL and order_id in mail_sent["subject"]
    assert "kl. 17:30" in mail_sent["body"] and "34750 kr" in mail_sent["body"] and f"/orders/{order_id}" in mail_sent["body"]


def test_submit_twice_does_not_create_two_orders(client, store):
    log_in(client, GOOD_CART)
    submit(client)
    res = submit(client)
    assert res.headers["Location"].endswith("/cart") and len(store.created) == 1


def test_submit_refused_by_database_keeps_cart(client, store):
    store.create_fails = True  # e.g. the admin raised the minimum in the meantime
    log_in(client, GOOD_CART)
    res = submit(client)
    assert res.headers["Location"].endswith("/cart")
    with client.session_transaction() as s:
        assert s["cart"] == GOOD_CART
    assert store.outbox == []


def order_row(order_id, status, payment="not_paid"):
    return {"id": order_id, "status": status, "payment_status": payment, "event_date": date(2026, 12, 3),
            "guests": 50, "total_nok": 34750, "event_type": WEDDING}


def test_order_history_lists_current_and_past(client, store):
    store.orders = {"EM-000001": (EMAIL, order_row("EM-000001", "delivered", "paid")),
                    "EM-000002": (EMAIL, order_row("EM-000002", "submitted")),
                    "EM-000003": ("someone@else.no", order_row("EM-000003", "submitted"))}
    log_in(client)
    html = client.get("/orders").get_data(as_text=True)
    current, past = html.split("Tidligere bestillinger")
    assert "EM-000002" in current and "Sendt inn" in current
    assert "EM-000001" in past and "Levert" in past and "Betalt" in past
    assert "EM-000003" not in html


def detail(status):
    return {**order_row("EM-000001", status), "payment_option": "invoice", "min_guests_at_order": 50,
            "delivery_address": "Bryggen 1", "delivery_notes": "",
            "lines": [{"id": "wedding-menu", "name_no": "Bryllupsmeny", "name_en": "Wedding menu", "quantity": 50,
                       "unit_price_nok": 695, "line_total": 34750}],
            "groups": [{"position": 1, "count": 4, "allergens": [ALLERGENS[0]], "diets": [DIETS[0]]}],
            "history": [{"to_status": "submitted", "at": datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc),
                         "by_role": "customer"}]}


def test_order_detail(client, store):
    store.orders = {"EM-000001": (EMAIL, detail("submitted"))}
    log_in(client)
    html = client.get("/orders/EM-000001").get_data(as_text=True)
    assert "Bestilling EM-000001" in html and "Bryllupsmeny" in html
    assert "4 gjester:</strong>" in html and "Gluten, Vegansk" in html
    assert "02.11.2026 13:00: Sendt inn" in html
    assert "kan ikke endres" not in html


def test_past_order_is_read_only(client, store):
    store.orders = {"EM-000001": (EMAIL, detail("delivered"))}
    log_in(client)
    html = client.get("/orders/EM-000001").get_data(as_text=True)
    assert "Denne bestillingen er avsluttet og kan ikke endres." in html
    assert "/change" not in html and "/cancel" not in html
    assert "/orders/EM-000001/questions" in html  # questions are still possible, e.g. about the invoice


def test_other_customers_order_is_not_found(client, store):
    store.orders = {"EM-000003": ("someone@else.no", detail("submitted"))}
    log_in(client)
    assert client.get("/orders/EM-000003").status_code == 404
    assert client.get("/orders").status_code == 200


def test_orders_need_login(client, store):
    assert client.get("/orders").status_code == 302


# --- development outbox ----------------------------------------------------------

def outbox_client(enabled, store):
    driver = FakeDriver()
    driver.handler = store
    return create_app({"TESTING": True, "NEO4J_DRIVER": driver, "DEV_OUTBOX": enabled}).test_client()


def test_outbox_page_only_in_development(store):
    assert outbox_client(False, store).get("/dev/outbox").status_code == 404
    store.outbox = [{"recipient": EMAIL, "subject": "Ekte Mat: bestilling EM-1 er mottatt", "body": "Hei"}]
    html = outbox_client(True, store).get("/dev/outbox").get_data(as_text=True)
    assert "Ekte Mat: bestilling EM-1 er mottatt" in html and EMAIL in html


def test_mail_send_never_raises(driver):
    def broken(query, params):
        raise RuntimeError("database down")
    driver.handler = broken
    app = create_app({"TESTING": True, "NEO4J_DRIVER": driver})
    with app.app_context():
        mail.send(EMAIL, "subject", "body")  # logged, not raised
