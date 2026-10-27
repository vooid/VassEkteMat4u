"""PIN login, kitchen screen, prep list and driver screen (US-27 – US-30) and questions (US-12, US-26)."""
from datetime import date, datetime, timezone

import pytest

from app import auth, create_app, orders
from app.repositories import devices
from app.repositories import kitchen as kitchen_repo
from app.repositories import orders as orders_repo
from app.repositories import questions
from tests.conftest import STAFF, log_in_staff

AT = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
LUNCH = {"name_no": "Firmalunsj", "name_en": "Corporate lunch"}
GLUTEN = {"code": "gluten", "name_no": "Gluten", "name_en": "Gluten"}
VEGAN = {"code": "vegan", "name_no": "Vegansk", "name_en": "Vegan"}


# --- PIN login ---------------------------------------------------------------------

DEVICE_TOKEN = "kitchen-tablet-token"


class PinStore:
    def __init__(self, locked=False):
        self.device_checks = []
        self.member = {**STAFF["kitchen"], "pin_hash": auth.hash_password("4321"), "failed_pin_attempts": 0,
                       "locked": locked}
        self.failed, self.succeeded = [], []

    def __call__(self, query, params):
        if query == devices.CHECK_QUERY:
            self.device_checks.append(params)
            return [{"device": {"id": "d1", "name": "Kjøkkennettbrett"}}] \
                if params["token_hash"] == auth.device_token_hash(DEVICE_TOKEN) else []
        if "s.pin_hash IS NOT NULL" in query and "$email" in query:
            return [{"s": self.member}] if params["email"] == self.member["email"] else []
        if "s.pin_hash IS NOT NULL" in query:
            return [{"s": {k: self.member[k] for k in ("email", "name", "role")}}]
        if "failed_pin_attempts + 1" in query or "coalesce(s.failed_pin_attempts, 0) + 1" in query:
            self.failed.append(params)
            return []
        if "SET s.failed_pin_attempts = 0" in query:
            self.succeeded.append(params["email"])
            return []
        if "MATCH (s:Staff {email: $email}) RETURN" in query:
            return [{"s": STAFF["kitchen"]}] if params["email"] == self.member["email"] else []
        return []


@pytest.fixture
def pins(client, driver):
    driver.handler = PinStore()
    client.set_cookie(auth.PIN_DEVICE_COOKIE, DEVICE_TOKEN)
    return driver.handler


def test_pin_login_only_on_approved_devices(client, pins):
    client.delete_cookie(auth.PIN_DEVICE_COOKIE)
    response = client.get("/staff/pin")
    assert response.status_code == 403 and "ikke godkjent for PIN-innlogging" in response.get_data(as_text=True)
    assert 'name="pin"' not in response.get_data(as_text=True)
    client.set_cookie(auth.PIN_DEVICE_COOKIE, "made-up-token")
    response = client.post("/staff/pin", data={"email": STAFF["kitchen"]["email"], "pin": "4321"})
    assert response.status_code == 403 and pins.succeeded == [] and pins.failed == []


def test_pin_login_lands_on_the_kitchen_screen(client, pins):
    page = client.get("/staff/pin").get_data(as_text=True)
    assert "Mateo" in page and 'inputmode="numeric"' in page
    response = client.post("/staff/pin", data={"email": STAFF["kitchen"]["email"], "pin": "4321"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/kitchen")
    assert pins.succeeded == [STAFF["kitchen"]["email"]]
    assert pins.device_checks[-1]["touch"] is True  # a login marks the device as used


def test_wrong_pin_is_counted(client, pins):
    response = client.post("/staff/pin", data={"email": STAFF["kitchen"]["email"], "pin": "0000"})
    assert response.status_code == 401 and "Feil navn eller PIN-kode." in response.get_data(as_text=True)
    assert pins.failed == [{"email": STAFF["kitchen"]["email"], "max": auth.MAX_PIN_ATTEMPTS,
                            "minutes": auth.PIN_LOCK_MINUTES}]


def test_blocked_pin_login_refuses_even_the_right_pin(client, driver):
    driver.handler = PinStore(locked=True)
    client.set_cookie(auth.PIN_DEVICE_COOKIE, DEVICE_TOKEN)
    response = client.post("/staff/pin", data={"email": STAFF["kitchen"]["email"], "pin": "4321"})
    assert response.status_code == 401 and "For mange feil forsøk" in response.get_data(as_text=True)
    assert driver.handler.succeeded == [] and driver.handler.failed == []


def test_admins_cannot_use_a_pin(driver):
    driver.handler = PinStore()
    with create_app({"TESTING": True, "NEO4J_DRIVER": driver}).app_context():
        assert auth.authenticate_pin(STAFF["admin"]["email"], "4321") == (None, False)
    assert all("roles" not in p or p["roles"] == list(auth.PIN_ROLES) for _, p in driver.queries)


def test_password_login_lands_on_the_role_home(client, driver):
    member = {**STAFF["driver"], "password_hash": auth.hash_password("hemmelig123")}
    driver.handler = lambda q, p: [{"s": member}] if p.get("email") == member["email"] else []
    response = client.post("/staff/login", data={"email": member["email"], "password": "hemmelig123"})
    assert response.headers["Location"].endswith("/driver")


@pytest.mark.parametrize("pin,role,message", [
    ("12", "kitchen", "4–8 digits"),
    ("1234", "admin", "admins use a password"),
])
def test_set_pin_validates(driver, pin, role, message):
    driver.handler = lambda q, p: [{"s": {**STAFF["kitchen"], "role": role}}] if "MATCH (s:Staff" in q else []
    app = create_app({"TESTING": True, "NEO4J_DRIVER": driver})
    result = app.test_cli_runner().invoke(args=["set-pin", STAFF["kitchen"]["email"], "--pin", pin])
    assert result.exit_code != 0 and message in result.output


def test_set_pin_stores_a_hash(driver):
    driver.handler = lambda q, p: [{"s": STAFF["kitchen"], "email": STAFF["kitchen"]["email"]}]
    app = create_app({"TESTING": True, "NEO4J_DRIVER": driver})
    result = app.test_cli_runner().invoke(args=["set-pin", STAFF["kitchen"]["email"], "--pin", "4321"])
    assert result.exit_code == 0, result.output
    params = [p for q, p in driver.queries if "SET s.pin_hash" in q][0]
    assert params["hash"] != "4321" and auth.check_password_hash(params["hash"], "4321")


class DeviceStore:
    def __init__(self):
        self.approved, self.revoked = [], []

    def __call__(self, query, params):
        if query == devices.APPROVE_QUERY:
            self.approved.append(params)
            return [{"id": "d1"}]
        if query == devices.CHECK_QUERY:
            ok = self.approved and params["token_hash"] == self.approved[-1]["token_hash"]
            return [{"device": {"id": "d1", "name": self.approved[-1]["name"]}}] if ok else []
        if query == devices.LIST_QUERY:
            return [{"device": {"id": "d1", "name": "Kjøkkennettbrett", "created_at": AT, "last_used_at": None,
                                "approved_by": "Ingrid"}}]
        if "DETACH DELETE d" in query:
            self.revoked.append(params["id"])
            return [{"done": 1}] if params["id"] == "d1" else []
        return []


def test_admin_approves_this_device(client, driver):
    store = DeviceStore()
    log_in_staff(client, driver, "admin", store)
    html = client.get("/admin/devices").get_data(as_text=True)
    assert "Kjøkkennettbrett" in html and "Ikke brukt ennå" in html and "Godkjenn denne enheten" in html

    response = client.post("/admin/devices", data={"name": "Kjøkkennettbrett"})
    cookie = response.headers["Set-Cookie"]
    assert cookie.startswith(auth.PIN_DEVICE_COOKIE + "=") and "HttpOnly" in cookie and "Max-Age=31536000" in cookie
    token = cookie.split(";")[0].split("=", 1)[1]
    [approved] = store.approved
    assert approved["token_hash"] == auth.device_token_hash(token) and token not in str(approved)
    assert approved["staff_email"] == STAFF["admin"]["email"]
    assert "Denne enheten er godkjent: Kjøkkennettbrett." in client.get("/admin/devices").get_data(as_text=True)

    client.post("/admin/devices", data={"name": " "})
    assert len(store.approved) == 1
    client.post("/admin/devices/d1/revoke")
    assert store.revoked == ["d1"]
    assert client.post("/admin/devices/nope/revoke").status_code == 404


def test_only_admins_manage_devices(client, driver):
    log_in_staff(client, driver, "kitchen", DeviceStore())
    assert client.get("/admin/devices").status_code == 403
    assert client.post("/admin/devices", data={"name": "Mitt"}).status_code == 403


# --- kitchen and driver screens -------------------------------------------------------

def kitchen_order(seen=None):
    return {"id": "EM-000001", "event_time": "11:30", "guests": 12, "delivery_notes": "Bakdøra", "event_type": LUNCH,
            "lines": [{"id": "fish-soup", "name_no": "Fiskesuppe", "name_en": "Fish soup", "quantity": 12}],
            "groups": [{"count": 2, "allergens": [GLUTEN], "diets": [VEGAN]}], "seen": seen}


class ScreenStore:
    def __init__(self):
        self.kitchen = [kitchen_order()]
        self.confirmed, self.status_changes = [], []
        self.prep = {"amounts": [], "missing": [], "unapproved": 0}

    def __call__(self, query, params):
        if query == kitchen_repo.KITCHEN_DAY_QUERY:
            self.day = params["day"]
            return [{"order": o} for o in self.kitchen]
        if query == kitchen_repo.CONFIRM_ALLERGIES_QUERY:
            self.confirmed.append(params)
            return [{"id": params["order_id"]}] if params["order_id"] == "EM-000001" else []
        if query == kitchen_repo.DRIVER_DAY_QUERY:
            return [{"order": {"id": "EM-000001", "status": "in_preparation", "event_time": "11:30", "guests": 12,
                               "delivery_address": "Bryggen 1, Bergen", "delivery_notes": "Bakdøra",
                               "event_type": LUNCH, "customer": {"name": "Kari", "phone": "+4799999999"},
                               "delivered": None}}]
        if query == kitchen_repo.PREP_LIST_QUERY:
            self.prep_params = params
            return [self.prep]
        if query == orders_repo.CHANGE_STATUS_QUERY:
            self.status_changes.append(params)
            return [{"id": params["order_id"]}]
        return []


@pytest.fixture
def screens(driver):
    return ScreenStore()


def test_kitchen_screen_shows_dishes_and_allergies_in_red(client, driver, screens):
    log_in_staff(client, driver, "kitchen", screens)
    html = client.get("/kitchen?day=2026-11-20").get_data(as_text=True)
    assert screens.day == "2026-11-20"
    assert "<strong>12</strong> × Fiskesuppe" in html and '<span class="time">11:30</span>' in html
    assert '<span class="allergy">Gluten</span>' in html and '<span class="diet">Vegansk</span>' in html
    assert "/kitchen/orders/EM-000001/allergies-seen" in html and 'http-equiv="refresh"' in html
    assert "?day=2026-11-19" in html and "?day=2026-11-21" in html


def test_kitchen_screen_defaults_to_today(client, driver, screens, monkeypatch):
    monkeypatch.setattr(orders, "today", lambda: date(2026, 11, 2))
    log_in_staff(client, driver, "kitchen", screens)
    client.get("/kitchen?day=nonsense")
    assert screens.day == "2026-11-02"


def test_allergies_seen_is_stored_once_and_shown(client, driver, screens):
    log_in_staff(client, driver, "kitchen", screens)
    response = client.post("/kitchen/orders/EM-000001/allergies-seen", data={"day": "2026-11-20"})
    assert response.headers["Location"].endswith("/kitchen?day=2026-11-20#order-EM-000001")
    assert screens.confirmed == [{"order_id": "EM-000001", "staff_email": STAFF["kitchen"]["email"]}]
    assert client.post("/kitchen/orders/EM-999999/allergies-seen").status_code == 404

    screens.kitchen = [kitchen_order(seen={"by": "Mateo", "at": AT})]
    html = client.get("/kitchen").get_data(as_text=True)
    assert "Allergier sett av Mateo 02.11.2026 13:00" in html and "allergies-seen" not in html


def test_driver_screen_and_delivery(client, driver, screens):
    log_in_staff(client, driver, "driver", screens)
    html = client.get("/driver").get_data(as_text=True)
    assert "query=Bryggen%201%2C%20Bergen" in html and '<span class="time">11:30</span>' in html and 'href="tel:+4799999999"' in html
    client.post("/driver/orders/EM-000001/delivered", data={"day": "2026-11-20"})
    [change] = screens.status_changes
    assert (change["order_id"], change["from_status"], change["to_status"], change["staff_email"]) == \
        ("EM-000001", "in_preparation", "delivered", STAFF["driver"]["email"])


def ingredient(id_, name_no, unit, day, amount):
    return {"id": id_, "name_no": name_no, "name_en": name_no, "unit": unit, "day": day, "amount": amount}


def test_prep_list_sums_ingredients_for_three_days(client, driver, screens, monkeypatch):
    monkeypatch.setattr(orders, "today", lambda: date(2026, 11, 2))
    screens.prep = {"amounts": [ingredient("cod", "Torskefilet", "kg", "2026-11-02", 0.12 * 25),
                                ingredient("cod", "Torskefilet", "kg", "2026-11-04", 1.5),
                                ingredient("eggs", "Egg", "pcs", "2026-11-03", 0.5 * 25),
                                ingredient("cream", "Fløte", "l", "2026-11-03", 0.08 * 12)],
                    "missing": [{"name_no": "Rakfisk-smaking", "name_en": "Rakfisk tasting", "portions": 10}],
                    "unapproved": 2}
    log_in_staff(client, driver, "kitchen", screens)
    html = client.get("/kitchen/prep").get_data(as_text=True)
    assert screens.prep_params == {"first": "2026-11-02", "last": "2026-11-04", "statuses": ["approved", "in_preparation"]}
    assert "Prepliste 02.11.2026 – 04.11.2026" in html
    # Rows sorted by name; kilos with a decimal comma, pieces rounded up, "–" on days without the ingredient.
    assert html.index(">Egg<") < html.index(">Fløte<") < html.index(">Torskefilet<")
    cod = html[html.index(">Torskefilet<"):]
    assert ['3 kg', '–', '1,5 kg'] == [c.split("<")[0] for c in cod.split('class="num">')[1:4]]
    assert "<strong>4,5 kg</strong>" in cod
    assert "13 stk" in html and "0,96 l" in html
    assert "Bestillinger som venter på godkjenning, er ikke tatt med: 2." in html
    assert "Rakfisk-smaking: 10 porsjoner" in html


def test_prep_list_empty(client, driver, screens):
    log_in_staff(client, driver, "admin", screens)
    html = client.get("/kitchen/prep").get_data(as_text=True)
    assert "Ingen bestillinger de neste 3 dagene." in html and "<table" not in html


def test_kitchen_pages_work_offline_on_the_tablet_only(client, driver, screens):
    log_in_staff(client, driver, "kitchen", screens)
    html = client.get("/kitchen").get_data(as_text=True)
    assert 'id="offline-warning"' in html and 'data-updated="' in html
    assert 'serviceWorker.register("/kitchen/sw.js", {scope: "/kitchen"})' in html
    log_in_staff(client, driver, "admin", screens)
    html = client.get("/kitchen").get_data(as_text=True)
    assert 'id="offline-warning"' in html and "serviceWorker.register" not in html  # not on the admin's laptop


def test_service_worker_may_control_the_kitchen_pages(client):
    response = client.get("/kitchen/sw.js")
    assert response.status_code == 200 and "javascript" in response.mimetype
    assert response.headers["Service-Worker-Allowed"] == "/kitchen" and response.headers["Cache-Control"] == "no-cache"
    assert "caches.match" in response.get_data(as_text=True)


def test_logout_clears_the_offline_copy(client, driver, screens):
    log_in_staff(client, driver, "kitchen", screens)
    response = client.post("/logout")
    assert response.headers["Clear-Site-Data"] == '"cache", "storage"'


@pytest.mark.parametrize("role,path,allowed", [
    ("kitchen", "/kitchen", True), ("kitchen", "/driver", False), ("kitchen", "/admin/orders", False),
    ("driver", "/driver", True), ("driver", "/kitchen", False),
    ("admin", "/kitchen", True), ("admin", "/driver", True),
    ("kitchen", "/kitchen/prep", True), ("admin", "/kitchen/prep", True), ("driver", "/kitchen/prep", False),
])
def test_screens_per_role(client, driver, screens, role, path, allowed):
    log_in_staff(client, driver, role, screens)
    assert client.get(path).status_code == (200 if allowed else 403)


def test_screens_need_staff_login(client, driver, screens):
    driver.handler = screens
    response = client.get("/kitchen")
    assert response.status_code == 302 and "/staff/login" in response.headers["Location"]


# --- questions (US-12, US-26) --------------------------------------------------------

def test_question_error():
    assert orders.question_error("") == "question_empty"
    assert orders.question_error("x" * (orders.MAX_QUESTION_LENGTH + 1)) == "question_too_long"
    assert orders.question_error("Kan vi få levert kl. 11?") is None


EMAIL = "kari@example.no"
ORDER = {"id": "EM-000001", "status": "approved", "payment_status": "not_paid", "payment_option": "invoice",
         "event_type": {"id": "corporate-lunch", **LUNCH}, "event_date": date(2026, 12, 1), "guests": 12,
         "min_guests_at_order": 8, "delivery_address": "Bryggen 1", "delivery_notes": "", "total_nok": 2268,
         "lines": [], "groups": [], "history": []}


class QuestionStore:
    def __init__(self):
        self.asked, self.answered, self.outbox = [], [], []
        self.list = [{"id": "q1", "text": "Kan vi få levert kl. 11?", "created_at": AT, "answer": None}]

    def __call__(self, query, params):
        if query == orders_repo.DETAIL_QUERY:
            return [{"order": ORDER}] if params["email"] == EMAIL and params["order_id"] == ORDER["id"] else []
        if query == orders_repo.ADMIN_DETAIL_QUERY:
            return [{"order": ORDER, "customer": {"email": EMAIL, "name": "Kari", "language": "en"}}]
        if query == questions.ASK_QUERY:
            self.asked.append(params)
            return [{"id": "q2"}]
        if query == questions.FOR_ORDER_QUERY:
            self.for_order_email = params["email"]
            return [{"question": q} for q in self.list]
        if query == questions.ANSWER_QUERY:
            self.answered.append(params)
            if len(self.answered) > 1:
                return []
            return [{"order": {"id": ORDER["id"], "event_date": ORDER["event_date"], "event_type": LUNCH},
                     "customer": {"email": EMAIL, "name": "Kari", "language": "en"},
                     "question": "Can you deliver at 11?"}]
        if query == questions.UNANSWERED_QUERY:
            return [{"question": {"id": "q1", "text": "Kan vi få levert kl. 11?", "created_at": AT,
                                  "order_id": "EM-000001", "event_date": ORDER["event_date"], "status": "approved",
                                  "event_type": LUNCH, "customer": {"name": "Kari", "email": EMAIL}}}]
        if "MATCH (s:Staff {role: 'admin'})" in query:
            return [{"email": STAFF["admin"]["email"]}]
        if "CREATE (:OutboxMessage" in query:
            self.outbox.append(params)
            return []
        if "MATCH (c:Customer {email: $email})" in query:
            return [{"c": {"email": EMAIL, "name": "Kari", "phone": "", "language": "no"}}] \
                if params.get("email") == EMAIL else []
        return []


@pytest.fixture
def qstore(driver):
    driver.handler = QuestionStore()
    return driver.handler


def log_in_customer(client):
    with client.session_transaction() as s:
        s["_user_id"] = f"customer:{EMAIL}"
        s["_fresh"] = True


def test_customer_sees_questions_and_can_ask(client, qstore):
    log_in_customer(client)
    html = client.get("/orders/EM-000001").get_data(as_text=True)
    assert qstore.for_order_email == EMAIL  # only the customer's own questions
    assert "Kan vi få levert kl. 11?" in html and "Venter på svar" in html

    response = client.post("/orders/EM-000001/questions", data={"text": "  Kan dere ta med duker?  "})
    assert response.headers["Location"].endswith("/orders/EM-000001#questions")
    assert qstore.asked == [{"email": EMAIL, "order_id": "EM-000001", "text": "Kan dere ta med duker?"}]
    mail = qstore.outbox[0]
    assert mail["recipient"] == STAFF["admin"]["email"]
    assert mail["subject"] == "Nytt spørsmål om bestilling EM-000001" and "Kan dere ta med duker?" in mail["body"]


def test_empty_question_and_someone_elses_order(client, qstore):
    log_in_customer(client)
    client.post("/orders/EM-000001/questions", data={"text": "   "})
    assert qstore.asked == [] and qstore.outbox == []
    assert client.post("/orders/EM-000009/questions", data={"text": "Hei"}).status_code == 404


def test_admin_answers_in_the_customers_language(client, driver, qstore):
    log_in_staff(client, driver, "admin", qstore)
    html = client.get("/admin/orders/EM-000001").get_data(as_text=True)
    assert qstore.for_order_email is None and "/admin/orders/EM-000001/questions/q1/answer" in html
    assert "Ubesvarte spørsmål" in client.get("/admin/questions").get_data(as_text=True)

    client.post("/admin/orders/EM-000001/questions/q1/answer", data={"text": "Yes, at 11."})
    assert qstore.answered[0] == {"order_id": "EM-000001", "question_id": "q1",
                                  "staff_email": STAFF["admin"]["email"], "text": "Yes, at 11."}
    mail = qstore.outbox[0]
    assert mail["recipient"] == EMAIL and mail["subject"] == "Ekte Mat: answer to your question about order EM-000001"
    assert "Can you deliver at 11?" in mail["body"] and "Yes, at 11." in mail["body"]

    response = client.post("/admin/orders/EM-000001/questions/q1/answer", data={"text": "Again"},
                           follow_redirects=True)
    assert "allerede besvart" in response.get_data(as_text=True) and len(qstore.outbox) == 1


def test_answered_question_shows_on_the_customer_page(client, qstore):
    qstore.list[0]["answer"] = {"text": "Ja, kl. 11.", "created_at": AT, "by": "Ingrid"}
    log_in_customer(client)
    html = client.get("/orders/EM-000001").get_data(as_text=True)
    assert "Svar fra Ingrid, 02.11.2026 13:00" in html and "Ja, kl. 11." in html
