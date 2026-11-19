from backend import app as auth_app
from backend.tests.conftest import create_broker, login, patch_json, post_json, register


def test_owner_listing_renter_application_and_owner_decision(client):
    owner = client
    renter = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Home Owner")
    register(renter, "renter@example.test", "renter", "Future Renter")

    created = post_json(owner, "/api/properties", {
        "title": "Garden Flat", "address": "12 Park Road, Pune",
        "description": "Quiet two bedroom home", "monthly_rent": 28000, "bedrooms": 2,
    })
    assert created.status_code == 201
    property_id = created.get_json()["property"]["id"]
    assert owner.get("/api/properties").get_json()["properties"][0]["title"] == "Garden Flat"
    assert renter.get("/api/properties").get_json()["properties"][0]["id"] == property_id

    forbidden_listing = post_json(renter, "/api/properties", {
        "title": "Fake listing", "address": "Somewhere in Pune", "monthly_rent": 1,
    })
    assert forbidden_listing.status_code == 403

    application = post_json(renter, "/api/applications", {"property_id": property_id, "message": "I can move next month."})
    assert application.status_code == 201
    application_id = application.get_json()["id"]
    assert post_json(renter, "/api/applications", {"property_id": property_id}).status_code == 409
    assert len(owner.get("/api/applications").get_json()["applications"]) == 1
    assert len(renter.get("/api/applications").get_json()["applications"]) == 1

    decision = post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Accepted"})
    assert decision.status_code == 200
    assert renter.get("/api/applications").get_json()["applications"][0]["status"] == "Accepted"
    assert renter.get("/api/properties").get_json()["properties"] == []
    assert post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Declined"}).status_code == 404


def test_commission_is_manual_broker_only_and_requires_accepted_application(client):
    owner = client
    renter = auth_app.app.test_client()
    broker = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Home Owner")
    register(renter, "renter@example.test", "renter", "Future Renter")
    create_broker()
    assert login(broker, "broker@example.test").status_code == 200

    property_id = post_json(owner, "/api/properties", {
        "title": "Garden Flat", "address": "12 Park Road, Pune", "monthly_rent": 28000,
    }).get_json()["property"]["id"]
    app_id = post_json(renter, "/api/applications", {"property_id": property_id}).get_json()["id"]
    assert post_json(broker, "/api/commissions", {"application_id": app_id, "amount": 5000}).status_code == 409
    post_json(owner, f"/api/applications/{app_id}/decision", {"status": "Accepted"})

    commission = post_json(broker, "/api/commissions", {"application_id": app_id, "amount": 5000})
    assert commission.status_code == 201
    commission_id = commission.get_json()["id"]
    assert broker.get("/api/commissions").get_json()["commissions"][0]["amount"] == 5000
    assert patch_json(broker, f"/api/commissions/{commission_id}", {"status": "Paid"}).get_json()["status"] == "Paid"
    assert patch_json(broker, f"/api/commissions/{commission_id}", {"status": "Unknown"}).status_code == 400
    assert owner.get("/api/commissions").status_code == 403


def test_maintenance_ticket_access_lifecycle_filters_and_notes(client):
    owner = client
    renter = auth_app.app.test_client()
    broker = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Home Owner")
    register(renter, "renter@example.test", "renter", "Future Renter")
    create_broker()
    login(broker, "broker@example.test")
    property_id = post_json(owner, "/api/properties", {
        "title": "Garden Flat", "address": "12 Park Road, Pune", "monthly_rent": 28000,
    }).get_json()["property"]["id"]

    blocked = post_json(renter, "/api/tickets", {
        "property_id": property_id, "title": "Leaking tap", "description": "Tap is dripping all day",
    })
    assert blocked.status_code == 403
    app_id = post_json(renter, "/api/applications", {"property_id": property_id}).get_json()["id"]
    post_json(owner, f"/api/applications/{app_id}/decision", {"status": "Accepted"})

    created = post_json(renter, "/api/tickets", {
        "property_id": property_id, "title": "Leaking tap", "description": "Tap is dripping all day",
        "category": "Plumbing", "priority": "High",
    })
    assert created.status_code == 201
    ticket_id = created.get_json()["id"]
    assert renter.get("/api/tickets").get_json()["tickets"][0]["status"] == "Pending"
    assert len(owner.get("/api/tickets").get_json()["tickets"]) == 1
    broker_ticket = broker.get("/api/tickets").get_json()["tickets"][0]
    assert broker_ticket["category"] == "Plumbing"
    assert patch_json(broker, f"/api/tickets/{ticket_id}", {"status": "In Progress", "manager_note": "Plumber contacted"}).get_json()["status"] == "In Progress"
    updated = renter.get("/api/tickets").get_json()["tickets"][0]
    assert updated["manager_note"] == "Plumber contacted"
    assert patch_json(broker, f"/api/tickets/{ticket_id}", {"status": "Resolved", "manager_note": "Fixed"}).status_code == 200
    assert renter.get("/api/tickets").get_json()["tickets"][0]["status"] == "Resolved"
    assert patch_json(owner, f"/api/tickets/{ticket_id}", {"status": "Skipped"}).status_code == 403
    assert patch_json(broker, f"/api/tickets/{ticket_id}", {"status": "Not a status"}).status_code == 400
    assert patch_json(broker, "/api/tickets/9999", {"status": "Resolved"}).status_code == 404
