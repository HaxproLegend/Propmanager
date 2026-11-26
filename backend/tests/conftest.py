import pytest

from backend import app as auth_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_app, "DATABASE", tmp_path / "test-propmanager.sqlite3")
    # The test client talks plain HTTP; production defaults to secure cookies.
    monkeypatch.setattr(auth_app, "COOKIE_SECURE", False)
    auth_app._initialized_database = None
    auth_app.app.config.update(TESTING=True)
    auth_app.init_db()
    with auth_app.app.test_client() as test_client:
        yield test_client


def post_json(client, path, payload):
    csrf = client.get("/api/auth/csrf").get_json()["csrfToken"]
    return client.post(path, json=payload, headers={"X-CSRF-Token": csrf})


def patch_json(client, path, payload):
    csrf = client.get("/api/auth/csrf").get_json()["csrfToken"]
    return client.patch(path, json=payload, headers={"X-CSRF-Token": csrf})


def register(client, email, role="renter", name="Test Person"):
    response = post_json(client, "/api/auth/register", {
        "name": name,
        "email": email,
        "password": "correct horse battery staple",
        "role": role,
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()["user"]


def create_broker(email="broker@example.test"):
    with auth_app.connect() as db:
        cursor = db.execute(
            "INSERT INTO users(email,name,role,password_hash,created_at) VALUES(?,?,?,?,?)",
            (email, "Demo Broker", "broker", auth_app.hasher.hash("correct horse battery staple"), 1),
        )
        return cursor.lastrowid


def login(client, email, password="correct horse battery staple"):
    return post_json(client, "/api/auth/login", {"email": email, "password": password})
