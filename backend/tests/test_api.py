def test_health_ok(client):
    assert client.get("/api/health").get_json() == {"status": "ok", "neo4j": "connected"}


def test_health_reports_unreachable_database(client, driver):
    driver.reachable = False
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.get_json()["neo4j"] == "unreachable"


def test_list_event_types(client, driver):
    driver.rows = [{"e": {"id": "wedding", "min_guests": 50}}]
    assert client.get("/api/event-types").get_json() == [{"id": "wedding", "min_guests": 50}]


def test_update_minimum(client, driver):
    driver.rows = [{"e": {"id": "wedding", "min_guests": 60}}]
    res = client.put("/api/event-types/wedding/minimum", json={"min_guests": 60})
    assert res.status_code == 200
    assert driver.queries[-1][1] == {"id": "wedding", "min": 60}


def test_update_minimum_unknown_event_type(client, driver):
    driver.rows = []
    assert client.put("/api/event-types/nope/minimum", json={"min_guests": 10}).status_code == 404


def test_update_minimum_rejects_out_of_range_values(client, driver):
    for bad in (0, 266, "20", 12.5, True, None):
        res = client.put("/api/event-types/wedding/minimum", json={"min_guests": bad})
        assert res.status_code == 400, bad
    assert driver.queries == []
