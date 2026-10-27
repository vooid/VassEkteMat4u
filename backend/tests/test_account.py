import pytest
from neo4j.exceptions import ConstraintError

from app import auth


class CustomerStore:
    """Fake Neo4j for :Customer queries."""

    def __init__(self):
        self.customers = {}

    def __call__(self, query, params):
        email = params.get("email")
        c = self.customers.get(email)
        if "CREATE (c:Customer" in query:
            if c:
                raise ConstraintError("already exists")
            self.customers[email] = {"email": email, "password_hash": params["hash"], "name": params["name"],
                                     "phone": params["phone"], "language": params["language"]}
            return [{"c": self._public(self.customers[email])}]
        if "SET c.language" in query:
            if c:
                c["language"] = params["language"]
            return []
        if "MATCH (c:Customer" in query:
            if not c:
                return []
            return [{"c": c if ".password_hash" in query else self._public(c)}]
        return []  # menu / cart queries: empty

    @staticmethod
    def _public(c):
        return {k: v for k, v in c.items() if k != "password_hash"}


@pytest.fixture
def store(driver):
    driver.handler = CustomerStore()
    return driver.handler


def register(client, email="kari@example.no", password="hemmelig123", password2=None, name="Kari", next_=None):
    url = "/register" + (f"?next={next_}" if next_ else "")
    return client.post(url, data={"name": name, "email": email, "phone": "",
                                  "password": password, "password2": password2 or password})


def logged_in_as(client):
    with client.session_transaction() as s:
        return s.get("_user_id")


def test_register_logs_in_and_stores_hash(client, store):
    res = register(client, email="  Kari@Example.NO ")
    assert res.status_code == 302
    assert logged_in_as(client) == "customer:kari@example.no"
    saved = store.customers["kari@example.no"]
    assert saved["password_hash"] != "hemmelig123" and saved["password_hash"].startswith(("scrypt:", "pbkdf2:"))
    assert saved["language"] == "no"
    assert "Kari" in client.get("/").get_data(as_text=True)  # name in header


def test_register_duplicate_email(client, store):
    register(client)
    client.post("/logout")
    res = register(client, password="annethemmelig")
    assert res.status_code == 400
    assert "Det finnes allerede en konto" in res.get_data(as_text=True)
    assert logged_in_as(client) is None


@pytest.mark.parametrize("kwargs,message", [
    ({"email": "not-an-email"}, "Skriv inn en gyldig e-postadresse."),
    ({"password": "short"}, "Passordet må ha 8–128 tegn."),
    ({"password2": "different123"}, "Passordene er ikke like."),
    ({"name": "  "}, "Skriv inn navnet ditt."),
])
def test_register_validation(client, store, kwargs, message):
    res = register(client, **kwargs)
    assert res.status_code == 400 and message in res.get_data(as_text=True)
    assert store.customers == {}


def test_login_and_logout(client, store):
    register(client)
    client.post("/logout")
    assert logged_in_as(client) is None
    res = client.post("/login", data={"email": "KARI@example.no", "password": "hemmelig123"})
    assert res.status_code == 302 and logged_in_as(client) == "customer:kari@example.no"


@pytest.mark.parametrize("email,password", [("kari@example.no", "wrong-password"), ("nobody@example.no", "x")])
def test_login_failure_is_generic(client, store, email, password):
    register(client)
    client.post("/logout")
    res = client.post("/login", data={"email": email, "password": password})
    assert res.status_code == 401
    assert "Feil e-post eller passord." in res.get_data(as_text=True)
    assert logged_in_as(client) is None


def test_login_redirects_to_next_but_not_off_site(client, store):
    register(client)
    client.post("/logout")
    res = client.post("/login?next=/cart", data={"email": "kari@example.no", "password": "hemmelig123"})
    assert res.headers["Location"] == "/cart"
    client.post("/logout")
    res = client.post("/login?next=https://evil.example/", data={"email": "kari@example.no", "password": "hemmelig123"})
    assert res.headers["Location"] == "/"


def test_cart_survives_login(client, store):
    register(client)
    client.post("/logout")
    with client.session_transaction() as s:
        s["cart"] = {"event_type": "wedding", "guests": 60, "items": {"layer-cake": 60}}
    client.post("/login", data={"email": "kari@example.no", "password": "hemmelig123"})
    with client.session_transaction() as s:
        assert s["cart"]["items"] == {"layer-cake": 60}


def test_language_saved_on_account_and_restored_on_login(client, store):
    register(client)
    client.post("/language/en", data={"next": "/"})
    assert store.customers["kari@example.no"]["language"] == "en"
    client.post("/logout")
    client.post("/language/no", data={"next": "/"})  # anonymous visitor switches back to Norwegian
    client.post("/login", data={"email": "kari@example.no", "password": "hemmelig123"})
    with client.session_transaction() as s:
        assert s["lang"] == "en"


def test_logout_requires_post_and_login(client, store):
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302  # not logged in: sent to login page


def test_cart_asks_anonymous_visitor_to_log_in(client, driver, store):
    with client.session_transaction() as s:
        s["cart"] = {"event_type": "wedding", "guests": 60, "items": {"layer-cake": 60}}
    cart_row = {"event_type": {"id": "wedding", "name_no": "Bryllup", "min_guests": 50},
                "dishes": [{"id": "layer-cake", "name_no": "Bløtkake", "price_nok": 85, "min_order_qty": 10}]}
    driver.handler = lambda query, params: [cart_row] if "SUITS" in query else store(query, params)
    html = client.get("/cart").get_data(as_text=True)
    assert "Logg inn for å bestille" in html and "/login?next=/cart" in html


def test_registration_errors_function():
    assert auth.registration_errors("a@b.no", "12345678", "12345678", "A") == []
    assert ("email_invalid", {}) in auth.registration_errors("a@b", "12345678", "12345678", "A")
