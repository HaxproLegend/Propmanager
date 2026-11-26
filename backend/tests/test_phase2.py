from datetime import datetime, timezone

from backend import app as auth_app
from backend.tests.conftest import create_broker, login, patch_json, post_json, register


def delete_json(client, path):
    csrf = client.get("/api/auth/csrf").get_json()["csrfToken"]
    return client.delete(path, headers={"X-CSRF-Token": csrf})


def make_org(owner, name="Northstar Property Partners", slug="northstar"):
    return post_json(owner, "/api/orgs", {"name": name, "slug": slug})


def test_org_creation_invitations_and_membership(client):
    owner = client
    other_owner = auth_app.app.test_client()
    manager = auth_app.app.test_client()
    broker = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Portfolio Owner")
    register(other_owner, "other@example.test", "owner", "Other Owner")
    create_broker()
    assert login(broker, "broker@example.test").status_code == 200

    created = make_org(owner)
    assert created.status_code == 201
    org_id = created.get_json()["organization"]["id"]
    assert created.get_json()["organization"]["member_role"] == "org_admin"
    assert other_owner.get(f"/api/orgs/{org_id}").status_code == 403
    assert broker.get(f"/api/orgs/{org_id}").status_code == 200
    assert [row["id"] for row in owner.get("/api/orgs").get_json()["organizations"]] == [org_id]

    invited = post_json(owner, f"/api/orgs/{org_id}/invitations", {
        "email": "manager@example.test", "role": "manager",
    })
    assert invited.status_code == 201
    token = invited.get_json()["token"]
    assert post_json(manager, f"/api/orgs/invitations/{token}/accept", {}).status_code == 401

    register(manager, "manager@example.test", "renter", "Operations Manager")
    accepted = post_json(manager, f"/api/orgs/invitations/{token}/accept", {})
    assert accepted.status_code == 200
    assert accepted.get_json()["role"] == "manager"
    assert post_json(manager, f"/api/orgs/invitations/{token}/accept", {}).status_code == 404
    roles = {row["email"]: row["role"] for row in owner.get(f"/api/orgs/{org_id}/members").get_json()["members"]}
    assert roles["manager@example.test"] == "manager"

    assert patch_json(owner, f"/api/orgs/{org_id}/members/{manager.get('/api/auth/me').get_json()['user']['id']}", {
        "role": "accountant",
    }).status_code == 200
    assert delete_json(owner, f"/api/orgs/{org_id}/members/{manager.get('/api/auth/me').get_json()['user']['id']}").status_code == 200
    assert manager.get(f"/api/orgs/{org_id}").status_code == 403


def test_org_commission_terms_override_default_rate(client):
    owner = client
    renter = auth_app.app.test_client()
    broker = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Portfolio Owner")
    register(renter, "renter@example.test")
    create_broker()
    login(broker, "broker@example.test")
    org_id = make_org(owner).get_json()["organization"]["id"]

    property_id = post_json(owner, "/api/properties", {
        "title": "Cedar Business Park", "address": "Hinjawadi, Pune", "monthly_rent": 20000, "unit_count": 2,
    }).get_json()["property"]["id"]
    assert post_json(owner, f"/api/orgs/{org_id}/properties/{property_id}", {}).status_code == 200
    assert post_json(owner, f"/api/orgs/{org_id}/commission-terms", {
        "party": "owner", "rate_basis_points": 900, "effective_from": "2020-01-01",
    }).status_code == 201

    application_id = post_json(renter, "/api/applications", {"property_id": property_id}).get_json()["id"]
    assert post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Accepted"}).status_code == 200

    rows = broker.get("/api/commissions").get_json()["commissions"]
    row = next(row for row in rows if row["application_id"] == application_id)
    assert row["rate_basis_points"] == 900
    assert row["amount_paise"] == 180000  # 9% of 20,000 rupees, in paise

    period = datetime.now(timezone.utc).strftime("%Y-%m")
    assert post_json(broker, "/api/commissions/generate", {"billing_period": period}).get_json()["created"] == 0


def test_org_leads_dashboard_and_csv_export(client):
    owner = client
    other_owner = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Portfolio Owner")
    register(other_owner, "other@example.test", "owner", "Other Owner")
    org_id = make_org(owner).get_json()["organization"]["id"]

    lead_id = post_json(owner, f"/api/orgs/{org_id}/leads", {
        "name": "=FORMULA", "email": "lead@example.test", "phone": "99999", "source": "Referral",
    }).get_json()["lead"]["id"]
    assert patch_json(owner, f"/api/orgs/{org_id}/leads/{lead_id}", {
        "status": "Qualified", "notes": "Follow up next week",
    }).status_code == 200
    assert other_owner.get(f"/api/orgs/{org_id}/leads").status_code == 403

    property_id = post_json(owner, "/api/properties", {
        "title": "Garden Flats", "address": "12 Park Road, Pune", "monthly_rent": 28000, "unit_count": 2,
    }).get_json()["property"]["id"]
    post_json(owner, f"/api/orgs/{org_id}/properties/{property_id}", {})
    renter = auth_app.app.test_client()
    register(renter, "renter@example.test")
    application_id = post_json(renter, "/api/applications", {"property_id": property_id}).get_json()["id"]
    post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Accepted"})

    summary = owner.get(f"/api/orgs/{org_id}/dashboard").get_json()["summary"]
    assert summary["properties"] == 1
    assert summary["units"] == 2
    assert summary["occupied_units"] == 1
    assert summary["occupancy_percent"] == 50.0
    assert summary["active_rentals"] == 1
    assert summary["leads_by_status"]["Qualified"] == 1

    lead_csv = owner.get(f"/api/orgs/{org_id}/export.csv?type=leads")
    assert lead_csv.status_code == 200
    assert "text/csv" in lead_csv.headers["Content-Type"]
    assert "'=FORMULA" in lead_csv.get_data(as_text=True)
    assert "Follow up next week" in lead_csv.get_data(as_text=True)
    for kind in ("commissions", "properties", "issues"):
        assert owner.get(f"/api/orgs/{org_id}/export.csv?type={kind}").status_code == 200
    assert owner.get(f"/api/orgs/{org_id}/export.csv?type=bad").status_code == 400


def test_analytics_is_role_scoped_and_has_chart_data(client):
    owner = client
    renter = auth_app.app.test_client()
    broker = auth_app.app.test_client()
    register(owner, "owner@example.test", "owner", "Portfolio Owner")
    register(renter, "renter@example.test")
    create_broker()
    login(broker, "broker@example.test")

    property_id = post_json(owner, "/api/properties", {
        "title": "Garden Flats", "address": "12 Park Road, Pune", "monthly_rent": 28000,
    }).get_json()["property"]["id"]
    application_id = post_json(renter, "/api/applications", {"property_id": property_id}).get_json()["id"]
    post_json(owner, f"/api/applications/{application_id}/decision", {"status": "Accepted"})
    post_json(renter, "/api/tickets", {
        "property_id": property_id, "title": "Leaking tap", "description": "The tap keeps dripping",
        "category": "Plumbing",
    })

    renter_data = renter.get("/api/analytics").get_json()
    assert {row["label"] for row in renter_data["charts"]["applications_by_status"]} == {"Accepted"}
    assert "leads_by_status" not in renter_data["charts"]
    assert renter_data["kpis"][1]["label"] == "Active rentals"

    owner_data = owner.get("/api/analytics").get_json()
    assert owner_data["charts"]["properties_by_type"][0]["label"] == "Apartment"
    assert owner_data["properties"][0]["occupied"] == 1
    assert owner_data["monthly"]

    broker_data = broker.get("/api/analytics").get_json()
    assert "leads_by_status" in broker_data["charts"]
    assert broker_data["charts"]["tickets_by_status"]
    assert broker_data["charts"]["commissions_by_month"]
