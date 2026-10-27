from app.repositories.menu import menu_by_event_type

WEDDING = {
    "id": "wedding", "name_no": "Bryllup", "name_en": "Wedding", "min_guests": 50,
    "items": [{
        "id": "layer-cake", "name_no": "Bløtkake med bær", "name_en": "Cream layer cake with berries",
        "description_no": "Hjemmelaget.", "description_en": "Home-made.",
        "price_nok": 85, "min_order_qty": 10, "image": None,
        "allergens": [{"code": "milk", "name_no": "Melk", "name_en": "Milk"}],
        "diets": [{"code": "vegetarian", "name_no": "Vegetar", "name_en": "Vegetarian"}],
    }],
}
BIRTHDAY_EMPTY = {"id": "birthday", "name_no": "Bursdag", "name_en": "Birthday", "min_guests": 10, "items": []}


def test_menu_shows_event_types_and_cards_in_norwegian(client, driver):
    driver.rows = [{"event_type": WEDDING}, {"event_type": BIRTHDAY_EMPTY}]
    html = client.get("/").get_data(as_text=True)
    assert 'lang="nb"' in html
    assert "Bryllup" in html and "Minst 50 gjester" in html
    assert "Bløtkake med bær" in html and "85" in html
    assert "Melk" in html and "Vegetar" in html
    assert "Bilde kommer" in html  # placeholder when no approved image
    assert "Ingen retter for denne typen arrangement ennå." in html


def test_card_minimum_is_drawn_from_event_type(client, driver):
    driver.rows = [{"event_type": WEDDING}]
    # Event minimum 50 is larger than the dish's own minimum 10.
    assert "Minstebestilling: 50" in client.get("/").get_data(as_text=True)


def test_dish_minimum_wins_when_larger():
    from app import create_app
    from tests.conftest import FakeDriver

    driver = FakeDriver()
    lunch = dict(WEDDING, min_guests=8, items=[dict(WEDDING["items"][0], min_order_qty=12)])
    driver.rows = [{"event_type": lunch}]
    with create_app({"TESTING": True, "NEO4J_DRIVER": driver}).app_context():
        assert menu_by_event_type()[0]["items"][0]["minimum"] == 12


def test_switch_to_english_and_back(client, driver):
    driver.rows = [{"event_type": WEDDING}]
    res = client.post("/language/en", data={"next": "/"})
    assert res.status_code == 302 and res.headers["Location"] == "/"
    html = client.get("/").get_data(as_text=True)
    assert 'lang="en"' in html
    assert "Wedding" in html and "At least 50 guests" in html and "Cream layer cake with berries" in html
    client.post("/language/no", data={"next": "/"})
    assert "Bryllup" in client.get("/").get_data(as_text=True)


def test_unknown_language_is_ignored(client, driver):
    client.post("/language/de", data={"next": "/"})
    assert 'lang="nb"' in client.get("/").get_data(as_text=True)


def test_language_switch_does_not_redirect_off_site(client):
    for target in ("https://evil.example/", "//evil.example/", "javascript:alert(1)"):
        res = client.post("/language/en", data={"next": target})
        assert res.headers["Location"] == "/"


def test_approved_image_is_shown(client, driver):
    item = dict(WEDDING["items"][0], image="/static/uploads/cake.jpg")
    driver.rows = [{"event_type": dict(WEDDING, items=[item])}]
    html = client.get("/").get_data(as_text=True)
    assert 'src="/static/uploads/cake.jpg"' in html and "Bilde kommer" not in html
