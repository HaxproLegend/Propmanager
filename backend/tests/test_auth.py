from backend import app as auth_app
from backend.tests.conftest import login, patch_json, post_json, register


def test_health_and_auth_session_lifecycle(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
    assert client.get("/api/auth/me").status_code == 401

    created = post_json(client, "/api/auth/register", {
        "name": "Renter One", "email": "renter@example.test",
        "password": "correct horse battery staple", "role": "renter",
    })
    assert created.status_code == 201
    assert created.get_json()["user"]["role"] == "renter"
    session_cookie = next(value for value in created.headers.getlist("Set-Cookie") if value.startswith("pm_session="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=Lax" in session_cookie

    raw_token = client.get_cookie("pm_session").value
    with auth_app.connect() as db:
        row = db.execute("SELECT token_hash FROM auth_sessions").fetchone()
    assert row["token_hash"] != raw_token

    assert client.get("/api/auth/me").get_json()["user"]["email"] == "renter@example.test"
    profile = patch_json(client, "/api/auth/me", {"name": "Updated Renter"})
    assert profile.status_code == 200
    assert profile.get_json()["user"]["name"] == "Updated Renter"
    assert profile.get_json()["user"]["role"] == "renter"
    assert patch_json(client, "/api/auth/me", {"name": "x"}).status_code == 400
    signed_out = post_json(client, "/api/auth/logout", {})
    assert signed_out.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    assert login(client, "renter@example.test").status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_registration_validation_and_broker_role_is_not_public(client):
    assert post_json(client, "/api/auth/register", {
        "name": "Broker", "email": "broker@example.test",
        "password": "correct horse battery staple", "role": "broker",
    }).status_code == 400
    assert post_json(client, "/api/auth/register", {
        "name": "A", "email": "not-an-email", "password": "short", "role": "renter",
    }).status_code == 400

    register(client, "renter@example.test")
    duplicate = post_json(client, "/api/auth/register", {
        "name": "Duplicate", "email": "renter@example.test",
        "password": "correct horse battery staple", "role": "renter",
    })
    assert duplicate.status_code == 409


def test_bad_login_is_generic_and_throttled(client):
    register(client, "owner@example.test", role="owner")
    for _ in range(4):
        assert login(client, "owner@example.test", "wrong password here").status_code == 401
    fifth = login(client, "owner@example.test", "wrong password here")
    assert fifth.status_code == 401
    sixth = login(client, "owner@example.test", "correct horse battery staple")
    assert sixth.status_code == 429
    assert "owner@example.test" not in sixth.get_json()["error"]
    unknown_user = login(auth_app.app.test_client(), "missing@example.test", "wrong password here")
    assert unknown_user.status_code == 401
    assert unknown_user.get_json() == {"error": fifth.get_json()["error"]}


def test_csrf_is_required_for_mutations(client):
    response = client.post("/api/auth/register", json={
        "name": "No CSRF", "email": "no-csrf@example.test",
        "password": "correct horse battery staple", "role": "renter",
    })
    assert response.status_code == 403


def test_broker_cli_creates_a_non_public_account(client, monkeypatch):
    answers = iter(["broker@example.test", "Demo Broker", "correct horse battery staple"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    result = auth_app.app.test_cli_runner().invoke(args=["create-broker"])
    assert result.exit_code == 0, result.output
    assert login(auth_app.app.test_client(), "broker@example.test").status_code == 200

