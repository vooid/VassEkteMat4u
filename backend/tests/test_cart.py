import pytest

from app import cart, create_app

WEDDING = {"id": "wedding", "name_no": "Bryllup", "name_en": "Wedding", "min_guests": 50}
LUNCH = {"id": "corporate-lunch", "name_no": "Firmalunsj", "name_en": "Corporate lunch", "min_guests": 8}
CAKE = {"id": "layer-cake", "name_no": "Bløtkake", "name_en": "Layer cake", "price_nok": 85, "min_order_qty": 10}
MENU3 = {"id": "wedding-menu", "name_no": "Bryllupsmeny", "name_en": "Wedding menu", "price_nok": 695,
         "min_order_qty": 40}
SOUP = {"id": "fish-soup", "name_no": "Fiskesuppe", "name_en": "Fish soup", "price_nok": 189, "min_order_qty": 10}

CATALOGUE = {"wedding": (WEDDING, [CAKE, MENU3]), "corporate-lunch": (LUNCH, [SOUP])}


@pytest.fixture
def shop(driver):
    """Fake Neo4j answering the cart query from CATALOGUE."""
    def handler(query, params):
        event_type, dishes = CATALOGUE.get(params.get("event_type_id"), (None, []))
        if event_type is None:
            return []
        return [{"event_type": event_type, "dishes": [d for d in dishes if d["id"] in params["dish_ids"]]}]
    driver.handler = handler
    return driver


def add(client, dish, event_type="wedding", quantity=50):
    return client.post("/cart/add", data={"event_type": event_type, "dish": dish, "quantity": quantity})


# --- rules (US-06) ---------------------------------------------------------------

def test_dish_minimum_is_larger_of_event_and_dish_minimum():
    assert cart.dish_minimum(WEDDING, CAKE) == 50
    assert cart.dish_minimum(LUNCH, SOUP) == 10


@pytest.mark.parametrize("raw,expected", [("12", 12), (" 3 ", 3), ("0", None), ("-1", None),
                                          ("1.5", None), ("abc", None), ("", None), (None, None),
                                          ("10000", None), ("9999", 9999)])
def test_parse_quantity(raw, expected):
    assert cart.parse_quantity(raw) == expected


def test_problems():
    c = {"event_type": "wedding", "guests": None, "items": {"layer-cake": 40}}
    lines = cart.lines(c, WEDDING, [CAKE])
    assert cart.problems(c, WEDDING, lines) == [
        ("guests_missing", {}), ("dish_below_minimum", {"dish_id": "layer-cake", "n": 50})]
    c.update(guests=49, items={"layer-cake": 50})
    assert cart.problems(c, WEDDING, cart.lines(c, WEDDING, [CAKE])) == [("guests_below_minimum", {"n": 50})]
    c["guests"] = 50
    assert cart.problems(c, WEDDING, cart.lines(c, WEDDING, [CAKE])) == []
    assert cart.problems({"items": {}}, WEDDING, []) == [("cart_empty", {})]


def test_lines_and_total():
    c = {"event_type": "wedding", "guests": 60, "items": {"layer-cake": 60, "wedding-menu": 60}}
    lines = cart.lines(c, WEDDING, [CAKE, MENU3])
    assert [line["line_total"] for line in lines] == [5100, 41700]
    assert cart.total(lines) == 46800


# --- pages (US-05) ----------------------------------------------------------------

def test_add_to_cart_and_view(client, shop):
    res = add(client, "layer-cake", quantity=50)
    assert res.status_code == 302 and res.headers["Location"].endswith("/#wedding")
    html = client.get("/cart").get_data(as_text=True)
    assert "Bløtkake" in html and "4250 kr" in html
    assert "Skriv inn antall gjester." in html  # guests still missing
    assert 'class="badge">1<' in html


def test_adding_same_dish_twice_adds_up(client, shop):
    add(client, "layer-cake", quantity=50)
    add(client, "layer-cake", quantity=10)
    with client.session_transaction() as s:
        assert s["cart"]["items"] == {"layer-cake": 60}


def test_cart_ok_when_minimums_met(client, shop):
    add(client, "layer-cake", quantity=50)
    client.post("/cart/update", data={"guests": "55", "qty-layer-cake": "55"})
    html = client.get("/cart").get_data(as_text=True)
    assert "Handlekurven oppfyller minstekravene." in html
    assert "4675 kr" in html


def test_below_minimum_is_reported(client, shop):
    add(client, "layer-cake", quantity=20)
    client.post("/cart/update", data={"guests": "30"})
    html = client.get("/cart").get_data(as_text=True)
    assert "Dette arrangementet krever minst 50 gjester." in html
    assert "Bløtkake: minst 50 porsjoner." in html
    assert "Handlekurven oppfyller minstekravene." not in html


def test_invalid_update_keeps_old_values(client, shop):
    add(client, "layer-cake", quantity=50)
    client.post("/cart/update", data={"guests": "lots", "qty-layer-cake": "-3"})
    with client.session_transaction() as s:
        assert s["cart"]["items"] == {"layer-cake": 50} and s["cart"].get("guests") is None
    assert "Skriv et helt tall fra 1 til 9999." in client.get("/cart").get_data(as_text=True)


def test_cart_is_for_one_event_type(client, shop):
    add(client, "layer-cake", quantity=50)
    add(client, "fish-soup", event_type="corporate-lunch", quantity=10)
    with client.session_transaction() as s:
        assert s["cart"]["items"] == {"layer-cake": 50}
        assert ("error", "Handlekurven gjelder et annet arrangement. Tøm handlekurven for å bestille til dette.") \
            in s["_flashes"]


def test_cannot_add_dish_not_on_that_event_menu(client, shop):
    add(client, "fish-soup", event_type="wedding")
    with client.session_transaction() as s:
        assert "cart" not in s


def test_remove_and_clear(client, shop):
    add(client, "layer-cake")
    add(client, "wedding-menu")
    client.post("/cart/remove/layer-cake")
    with client.session_transaction() as s:
        assert s["cart"]["items"] == {"wedding-menu": 50}
    client.post("/cart/clear")
    with client.session_transaction() as s:
        assert "cart" not in s
    assert "Handlekurven er tom." in client.get("/cart").get_data(as_text=True)


def test_unavailable_dishes_are_dropped_on_view(client, shop):
    add(client, "layer-cake")
    add(client, "wedding-menu")
    CATALOGUE["wedding"] = (WEDDING, [MENU3])  # cake unpublished meanwhile
    try:
        html = client.get("/cart").get_data(as_text=True)
    finally:
        CATALOGUE["wedding"] = (WEDDING, [CAKE, MENU3])
    assert "Noen retter er ikke lenger tilgjengelige" in html
    with client.session_transaction() as s:
        assert s["cart"]["items"] == {"wedding-menu": 50}


def test_forms_require_csrf_token(driver):
    app = create_app({"TESTING": True, "NEO4J_DRIVER": driver})  # CSRF on, as in production
    res = app.test_client().post("/cart/add", data={"event_type": "wedding", "dish": "layer-cake", "quantity": 50})
    assert res.status_code == 400
