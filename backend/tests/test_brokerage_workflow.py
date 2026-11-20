from backend import app as auth_app
from backend.tests.conftest import create_broker, login, patch_json, post_json, register
from datetime import datetime, timezone


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
    assert owner.get("/api/dashboard").get_json()["summary"]["listings"] == 1
    assert renter.get("/api/dashboard").get_json()["summary"]["available_properties"] == 1

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
    assert renter.get("/api/dashboard").get_json()["summary"]["applications"] == 1
    assert post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Declined"}).status_code == 404


def test_monthly_commissions_are_generated_for_both_parties_and_stop_after_rental(client):
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
    assert broker.get("/api/commissions").get_json()["commissions"] == []
    post_json(owner, f"/api/applications/{app_id}/decision", {"status": "Accepted"})

    current_period = datetime.now(timezone.utc).strftime("%Y-%m")
    records = broker.get("/api/commissions").get_json()["commissions"]
    assert len(records) == 2
    assert {row["party"] for row in records} == {"owner", "renter"}
    assert {row["rate_basis_points"] for row in records} == {1000}
    assert {row["amount_paise"] for row in records} == {280000}
    assert {row["billing_period"] for row in records} == {current_period}
    assert broker.get("/api/dashboard").get_json()["summary"]["pending_commission_amount_paise"] == 560000

    again = post_json(broker, "/api/commissions/generate", {"billing_period": current_period})
    assert again.status_code == 201 and again.get_json()["created"] == 0
    assert post_json(broker, "/api/commissions/generate", {"billing_period": "bad"}).status_code == 400
    assert owner.get("/api/commissions").status_code == 403

    for row in records:
        assert patch_json(broker, f"/api/commissions/{row['id']}", {"status": "Paid"}).get_json()["status"] == "Paid"
        assert patch_json(broker, f"/api/commissions/{row['id']}", {"status": "Unknown"}).status_code == 400
    assert broker.get("/api/dashboard").get_json()["summary"]["pending_commission_amount_paise"] == 0

    assert post_json(owner, f"/api/applications/{app_id}/end", {"reason": "Lease ended"}).status_code == 200
    next_period = "2027-01" if current_period.endswith("12") else f"{current_period[:4]}-{int(current_period[-2:]) + 1:02d}"
    stopped = post_json(broker, "/api/commissions/generate", {"billing_period": next_period})
    assert stopped.get_json()["created"] == 0
    assert broker.get("/api/commissions").status_code == 200
    assert owner.get("/api/commissions").status_code == 403


def test_maintenance_ticket_access_lifecycle_filters_and_notes(client):
    owner = client
    renter = auth_app.app.test_client()
    broker = auth_app.app.test_client()
    other_renter = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Home Owner")
    register(renter, "renter@example.test", "renter", "Future Renter")
    register(other_renter, "other-renter@example.test", "renter", "Other Renter")
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
    details = renter.get(f"/api/tickets/{ticket_id}").get_json()
    assert len(details["history"]) == 2
    assert details["history"][0]["event_type"] == "created"
    assert details["history"][1]["event_type"] == "status_changed"
    assert details["ticket"]["similar_issue_count"] == 0
    assert owner.get(f"/api/tickets/{ticket_id}").status_code == 200
    assert other_renter.get(f"/api/tickets/{ticket_id}").status_code == 404
    assert patch_json(broker, f"/api/tickets/{ticket_id}", {"status": "Resolved", "manager_note": "Fixed"}).status_code == 200
    assert renter.get("/api/tickets").get_json()["tickets"][0]["status"] == "Resolved"
    assert patch_json(owner, f"/api/tickets/{ticket_id}", {"status": "Skipped"}).status_code == 403
    assert patch_json(broker, f"/api/tickets/{ticket_id}", {"status": "Not a status"}).status_code == 400
    assert patch_json(broker, "/api/tickets/9999", {"status": "Resolved"}).status_code == 404


def test_owner_can_edit_unrented_listing_and_control_availability(client):
    owner = client
    renter = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Home Owner")
    register(renter, "renter@example.test", "renter", "Future Renter")
    property_id = post_json(owner, "/api/properties", {
        "title": "Garden Flat", "address": "12 Park Road, Pune", "monthly_rent": 28000,
    }).get_json()["property"]["id"]

    updated = patch_json(owner, f"/api/properties/{property_id}", {
        "title": "Updated Garden Flat", "address": "14 Park Road, Pune", "monthly_rent": 30000,
        "bedrooms": 2, "description": "Updated listing", "status": "Unavailable",
    })
    assert updated.status_code == 200
    assert renter.get("/api/properties").get_json()["properties"] == []
    assert patch_json(renter, f"/api/properties/{property_id}", {
        "title": "Hijacked", "address": "14 Park Road, Pune", "monthly_rent": 30000,
    }).status_code == 403
    assert patch_json(owner, f"/api/properties/{property_id}", {
        "title": "Updated Garden Flat", "address": "14 Park Road, Pune", "monthly_rent": 30000,
        "bedrooms": 2, "description": "Updated listing", "status": "Rented",
    }).status_code == 400


def test_one_owner_and_renter_can_have_multiple_properties(client):
    owner = client
    renter = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Portfolio Owner")
    register(renter, "renter@example.test", "renter", "Multi-home Renter")
    home_ids = []
    for title, address, property_type in (("Garden Flat", "12 Park Road, Pune", "Apartment"), ("Office Tower", "9 Lake Road, Pune", "Office/Commercial")):
        created = post_json(owner, "/api/properties", {
            "title": title, "address": address, "monthly_rent": 28000,
            "property_type": property_type, "unit_count": 48,
        })
        assert created.status_code == 201
        assert created.get_json()["property"]["unit_count"] == 48
        home_ids.append(created.get_json()["property"]["id"])
    assert len(owner.get("/api/properties").get_json()["properties"]) == 2

    for property_id in home_ids:
        application = post_json(renter, "/api/applications", {"property_id": property_id})
        assert application.status_code == 201
        decision = post_json(owner, f"/api/applications/{application.get_json()['id']}/decision", {"status": "Accepted"})
        assert decision.status_code == 200
        ticket = post_json(renter, "/api/tickets", {
            "property_id": property_id, "title": "Small repair", "description": "A minor repair request",
        })
        assert ticket.status_code == 201

    assert len(renter.get("/api/applications").get_json()["applications"]) == 2
    assert len(renter.get("/api/tickets").get_json()["tickets"]) == 2
    assert renter.get("/api/dashboard").get_json()["summary"]["open_tickets"] == 2
