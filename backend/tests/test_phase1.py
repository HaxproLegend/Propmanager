from backend import app as auth_app
from backend.tests.conftest import create_broker, login, patch_json, post_json, register


def test_property_search_filters_and_units(client):
    owner = client
    renter = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Portfolio Owner")
    register(renter, "renter@example.test")

    first = post_json(owner, "/api/properties", {
        "title": "Lavender Apartments", "address": "Baner, Pune", "monthly_rent": 32000,
        "property_type": "Apartment", "unit_count": 3,
        "image_url": "https://images.example.test/lavender.jpg",
    })
    second = post_json(owner, "/api/properties", {
        "title": "Cedar Business Park", "address": "Hinjawadi, Pune", "monthly_rent": 185000,
        "property_type": "Office/Commercial", "unit_count": 2,
    })
    assert first.status_code == 201 and second.status_code == 201
    assert first.get_json()["property"]["image_url"].startswith("https://")

    found = renter.get("/api/properties?q=lavender").get_json()["properties"]
    assert [row["id"] for row in found] == [first.get_json()["property"]["id"]]
    assert renter.get("/api/properties?location=hinjawadi").get_json()["properties"][0]["id"] == second.get_json()["property"]["id"]
    assert {row["id"] for row in renter.get("/api/properties?min_rent=30000&max_rent=40000").get_json()["properties"]} == {first.get_json()["property"]["id"]}
    assert renter.get("/api/properties?property_type=Office%2FCommercial").get_json()["properties"][0]["id"] == second.get_json()["property"]["id"]
    assert renter.get("/api/properties?min_rent=bad").status_code == 400
    assert renter.get("/api/properties?property_type=Villa").status_code == 400

    property_id = first.get_json()["property"]["id"]
    units = renter.get(f"/api/properties/{property_id}/units").get_json()["units"]
    assert len(units) == 3
    assert {row["status"] for row in units} == {"Available"}
    assert renter.get("/api/properties").get_json()["properties"][0]["available_units"] == 3


def test_application_timeline_assigns_distinct_units_and_notifies(client):
    owner = client
    renter_one = auth_app.app.test_client()
    renter_two = auth_app.app.test_client()
    broker = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Portfolio Owner")
    register(renter_one, "one@example.test", name="Renter One")
    register(renter_two, "two@example.test", name="Renter Two")
    create_broker()
    login(broker, "broker@example.test")

    property_id = post_json(owner, "/api/properties", {
        "title": "Willow PG Rooms", "address": "Kothrud, Pune", "monthly_rent": 14500,
        "property_type": "PG/Hostel", "unit_count": 2,
    }).get_json()["property"]["id"]
    ids = []
    for renter in (renter_one, renter_two):
        application = post_json(renter, "/api/applications", {"property_id": property_id})
        assert application.status_code == 201
        ids.append(application.get_json()["id"])

    decisions = [post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Accepted"}) for application_id in ids]
    assert all(response.status_code == 200 for response in decisions)
    unit_ids = {response.get_json()["unit_id"] for response in decisions}
    assert len(unit_ids) == 2
    assert all(row["status"] == "Rented" for row in owner.get(f"/api/properties/{property_id}/units").get_json()["units"])

    detail = renter_one.get(f"/api/applications/{ids[0]}").get_json()
    assert [event["event_type"] for event in detail["history"]] == ["submitted", "decision"]
    assert detail["history"][1]["actor_name"] == "Portfolio Owner"
    assert renter_two.get(f"/api/applications/{ids[0]}").status_code == 404
    assert renter_one.get("/api/notifications").get_json()["unread"] >= 1
    assert broker.get("/api/notifications").get_json()["unread"] >= 2


def test_ticket_priority_sort_exposes_decision_factors(client):
    owner = client
    renter = auth_app.app.test_client()
    broker = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner")
    register(renter, "renter@example.test")
    create_broker()
    login(broker, "broker@example.test")

    property_id = post_json(owner, "/api/properties", {
        "title": "Garden Flat", "address": "12 Park Road, Pune", "monthly_rent": 28000,
    }).get_json()["property"]["id"]
    application_id = post_json(renter, "/api/applications", {"property_id": property_id}).get_json()["id"]
    post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Accepted"})
    for priority in ("Low", "Urgent", "High"):
        assert post_json(renter, "/api/tickets", {
            "property_id": property_id, "title": f"{priority} issue", "description": "A test issue",
            "priority": priority,
        }).status_code == 201

    tickets = broker.get("/api/tickets?sort=priority").get_json()["tickets"]
    assert [row["priority"] for row in tickets] == ["Urgent", "High", "Low"]
    assert all("age_hours" in row and "similar_resident_count" in row for row in tickets)


def test_notifications_can_be_read_individually_and_in_bulk(client):
    owner = client
    renter = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner")
    register(renter, "renter@example.test")
    property_id = post_json(owner, "/api/properties", {
        "title": "Garden Flat", "address": "12 Park Road, Pune", "monthly_rent": 28000,
    }).get_json()["property"]["id"]
    application_id = post_json(renter, "/api/applications", {"property_id": property_id}).get_json()["id"]
    post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Accepted"})

    response = renter.get("/api/notifications")
    assert response.status_code == 200
    notification_id = response.get_json()["notifications"][0]["id"]
    assert response.get_json()["unread"] >= 1
    assert patch_json(renter, f"/api/notifications/{notification_id}/read", {}).status_code == 200
    assert post_json(renter, "/api/notifications/read-all", {}).status_code == 200
    assert renter.get("/api/notifications").get_json()["unread"] == 0


def test_seed_demo_cli_is_idempotent_and_resettable(client):
    runner = auth_app.app.test_cli_runner()
    first = runner.invoke(args=["seed-demo"])
    assert first.exit_code == 0, first.output
    with auth_app.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM properties").fetchone()[0] == 8
        assert db.execute("SELECT COUNT(*) FROM maintenance_tickets").fetchone()[0] >= 8
        assert db.execute("SELECT COUNT(*) FROM notifications").fetchone()[0] >= 5

    again = runner.invoke(args=["seed-demo"])
    assert again.exit_code != 0
    assert "already seeded" in again.output

    reset = runner.invoke(args=["seed-demo", "--reset"])
    assert reset.exit_code == 0, reset.output
    with auth_app.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM users WHERE email LIKE '%@propmanager.demo'").fetchone()[0] == 5
