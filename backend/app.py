import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import Flask, jsonify, make_response, request


ROOT = Path(__file__).resolve().parent.parent
DATABASE = Path(os.environ.get("DATABASE_PATH", ROOT / "backend" / "instance" / "propmanager.sqlite3"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
hasher = PasswordHasher()


def connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('renter', 'owner', 'broker')),
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_attempts (
                email TEXT PRIMARY KEY,
                failed_count INTEGER NOT NULL DEFAULT 0,
                window_started INTEGER NOT NULL,
                locked_until INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                address TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                monthly_rent INTEGER NOT NULL,
                bedrooms INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'Available',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
                renter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                message TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at INTEGER NOT NULL,
                UNIQUE(property_id, renter_id)
            );
            CREATE TABLE IF NOT EXISTS commissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
                broker_id INTEGER NOT NULL REFERENCES users(id),
                amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS maintenance_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
                renter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Other',
                priority TEXT NOT NULL DEFAULT 'Medium',
                status TEXT NOT NULL DEFAULT 'Pending',
                manager_note TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
        """)


def api_error(message, status):
    return jsonify(error=message), status


def csrf_valid():
    cookie_token = request.cookies.get("pm_csrf", "")
    header_token = request.headers.get("X-CSRF-Token", "")
    return bool(cookie_token and header_token and hmac.compare_digest(cookie_token, header_token))


def require_csrf():
    if not csrf_valid():
        return api_error("Refresh the page and try again.", 403)
    return None


def current_user():
    raw_token = request.cookies.get("pm_session", "")
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = int(time.time())
    with connect() as db:
        row = db.execute("""
            SELECT u.id, u.email, u.name, u.role
            FROM auth_sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?
        """, (token_hash, now)).fetchone()
    return dict(row) if row else None


def set_csrf_cookie(response):
    csrf = secrets.token_urlsafe(32)
    response.set_cookie("pm_csrf", csrf, httponly=False, secure=COOKIE_SECURE,
                        samesite="Lax", path="/", max_age=60 * 60 * 24)
    return response


def issue_session(response, user_id):
    token = secrets.token_urlsafe(48)
    now = int(time.time())
    with connect() as db:
        db.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
        db.execute("INSERT INTO auth_sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                   (hashlib.sha256(token.encode()).hexdigest(), user_id, now + 60 * 60 * 24 * 7, now))
    response.set_cookie("pm_session", token, httponly=True, secure=COOKIE_SECURE,
                        samesite="Lax", path="/", max_age=60 * 60 * 24 * 7)
    return set_csrf_cookie(response)


app = Flask(__name__)
_initialized_database = None


@app.before_request
def initialize_database_for_current_path():
    global _initialized_database
    if _initialized_database != DATABASE:
        init_db()
        _initialized_database = DATABASE


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/auth/csrf")
def csrf():
    token = request.cookies.get("pm_csrf")
    if token:
        return jsonify(csrfToken=token)
    token = secrets.token_urlsafe(32)
    response = make_response(jsonify(csrfToken=token))
    response.set_cookie("pm_csrf", token, httponly=False, secure=COOKIE_SECURE,
                        samesite="Lax", path="/", max_age=60 * 60 * 24)
    return response


@app.post("/api/auth/register")
def register():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    role = str(body.get("role", "renter"))
    if len(name) < 2 or len(name) > 80:
        return api_error("Enter your name (2–80 characters).", 400)
    if len(email) > 254 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return api_error("Enter a valid email address.", 400)
    if len(password) < 12 or len(password) > 128:
        return api_error("Use a password between 12 and 128 characters.", 400)
    if role not in ("renter", "owner"):
        return api_error("Choose renter or owner. Broker accounts are created by a project administrator.", 400)
    try:
        with connect() as db:
            cursor = db.execute("INSERT INTO users(email, name, role, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                                (email, name, role, hasher.hash(password), int(time.time())))
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return api_error("We couldn't create an account with those details. Check the email or sign in.", 409)
    response = make_response(jsonify(user={"id": user_id, "email": email, "name": name, "role": role}), 201)
    return issue_session(response, user_id)


@app.post("/api/auth/login")
def login():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip().lower()[:254]
    password = str(body.get("password", ""))
    now = int(time.time())
    with connect() as db:
        attempt = db.execute("SELECT * FROM login_attempts WHERE email = ?", (email,)).fetchone()
        if attempt and attempt["locked_until"] > now:
            return api_error("Unable to sign in with those details. Try again later.", 429)
        user = db.execute("SELECT id, email, name, role, password_hash FROM users WHERE email = ?", (email,)).fetchone()
        valid = False
        if user:
            try:
                valid = hasher.verify(user["password_hash"], password)
            except (VerifyMismatchError, InvalidHashError):
                valid = False
        if not valid:
            started = attempt["window_started"] if attempt and now - attempt["window_started"] < 900 else now
            count = (attempt["failed_count"] + 1) if attempt and started == attempt["window_started"] else 1
            locked_until = now + 900 if count >= 5 else 0
            db.execute("INSERT INTO login_attempts(email, failed_count, window_started, locked_until) VALUES (?, ?, ?, ?) "
                       "ON CONFLICT(email) DO UPDATE SET failed_count=excluded.failed_count, window_started=excluded.window_started, locked_until=excluded.locked_until",
                       (email, count, started, locked_until))
            return api_error("Unable to sign in with those details.", 401)
        db.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
        public_user = {key: user[key] for key in ("id", "email", "name", "role")}
    response = make_response(jsonify(user=public_user))
    return issue_session(response, public_user["id"])


@app.get("/api/auth/me")
def me():
    user = current_user()
    if not user:
        return api_error("Sign in to continue.", 401)
    return jsonify(user=user)


def need_role(*roles):
    user = current_user()
    if not user:
        return None, api_error("Sign in to continue.", 401)
    if user["role"] not in roles:
        return None, api_error("You don't have access to this action.", 403)
    return user, None


def json_body():
    return request.get_json(silent=True) or {}


@app.get("/api/properties")
def list_properties():
    user = current_user()
    with connect() as db:
        if user and user["role"] == "owner":
            rows = db.execute("SELECT p.*, u.name owner_name FROM properties p JOIN users u ON u.id=p.owner_id WHERE p.owner_id=? ORDER BY p.created_at DESC", (user["id"],)).fetchall()
        elif user and user["role"] == "broker":
            rows = db.execute("SELECT p.*, u.name owner_name FROM properties p JOIN users u ON u.id=p.owner_id ORDER BY p.created_at DESC").fetchall()
        else:
            rows = db.execute("SELECT p.*, u.name owner_name FROM properties p JOIN users u ON u.id=p.owner_id WHERE p.status='Available' ORDER BY p.created_at DESC").fetchall()
    return jsonify(properties=[dict(row) for row in rows])


@app.post("/api/properties")
def create_property():
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner")
    if error: return error
    body = json_body()
    title, address = str(body.get("title", "")).strip(), str(body.get("address", "")).strip()
    description = str(body.get("description", "")).strip()[:1000]
    try: rent, bedrooms = int(body.get("monthly_rent")), int(body.get("bedrooms", 1))
    except (TypeError, ValueError): return api_error("Enter a valid rent and bedroom count.", 400)
    if not 3 <= len(title) <= 100 or not 5 <= len(address) <= 240 or rent < 1 or not 1 <= bedrooms <= 20:
        return api_error("Check the listing details and try again.", 400)
    with connect() as db:
        cur = db.execute("INSERT INTO properties(owner_id,title,address,description,monthly_rent,bedrooms,created_at) VALUES(?,?,?,?,?,?,?)", (user["id"], title, address, description, rent, bedrooms, int(time.time())))
        row = db.execute("SELECT p.*, u.name owner_name FROM properties p JOIN users u ON u.id=p.owner_id WHERE p.id=?", (cur.lastrowid,)).fetchone()
    return jsonify(property=dict(row)), 201


@app.get("/api/applications")
def list_applications():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    query = """SELECT a.*, p.title property_title, p.address, p.monthly_rent, r.name renter_name, r.email renter_email, o.name owner_name
               FROM applications a JOIN properties p ON p.id=a.property_id JOIN users r ON r.id=a.renter_id JOIN users o ON o.id=p.owner_id"""
    params = ()
    if user["role"] == "renter": query += " WHERE a.renter_id=?"; params = (user["id"],)
    elif user["role"] == "owner": query += " WHERE p.owner_id=?"; params = (user["id"],)
    query += " ORDER BY a.created_at DESC"
    with connect() as db: rows = db.execute(query, params).fetchall()
    return jsonify(applications=[dict(row) for row in rows])


@app.post("/api/applications")
def apply_for_property():
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("renter")
    if error: return error
    body = json_body()
    try: property_id = int(body.get("property_id"))
    except (TypeError, ValueError): return api_error("Choose a property first.", 400)
    message = str(body.get("message", "")).strip()[:1000]
    try:
        with connect() as db:
            cur = db.execute("INSERT INTO applications(property_id,renter_id,message,created_at) SELECT id,?,?,? FROM properties WHERE id=? AND status='Available'", (user["id"], message, int(time.time()), property_id))
            if not cur.rowcount: return api_error("That listing is no longer available.", 404)
            app_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return api_error("You have already applied for this property.", 409)
    return jsonify(id=app_id, status="Pending"), 201


@app.post("/api/applications/<int:application_id>/decision")
def decide_application(application_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner")
    if error: return error
    status = str(json_body().get("status", ""))
    if status not in ("Accepted", "Declined"): return api_error("Choose accept or decline.", 400)
    with connect() as db:
        cur = db.execute("UPDATE applications SET status=? WHERE id=? AND status='Pending' AND property_id IN (SELECT id FROM properties WHERE owner_id=? AND (?='Declined' OR status='Available'))", (status, application_id, user["id"], status))
        if not cur.rowcount: return api_error("Application not found or already decided.", 404)
        if status == "Accepted": db.execute("UPDATE properties SET status='Rented' WHERE id=(SELECT property_id FROM applications WHERE id=?)", (application_id,))
    return jsonify(status=status)


@app.get("/api/commissions")
def list_commissions():
    user, error = need_role("broker")
    if error: return error
    with connect() as db:
        rows = db.execute("""SELECT c.*, a.status application_status, p.title property_title, r.name renter_name, o.name owner_name
                            FROM commissions c JOIN applications a ON a.id=c.application_id JOIN properties p ON p.id=a.property_id
                            JOIN users r ON r.id=a.renter_id JOIN users o ON o.id=p.owner_id ORDER BY c.created_at DESC""").fetchall()
    return jsonify(commissions=[dict(row) for row in rows])


@app.post("/api/commissions")
def create_commission():
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("broker")
    if error: return error
    body = json_body()
    try: app_id, amount = int(body.get("application_id")), int(body.get("amount"))
    except (TypeError, ValueError): return api_error("Choose an accepted application and enter the fee.", 400)
    if amount < 1: return api_error("Commission must be greater than zero.", 400)
    try:
        with connect() as db:
            cur = db.execute("INSERT INTO commissions(application_id,broker_id,amount,created_at) SELECT id,?,?,? FROM applications WHERE id=? AND status='Accepted'", (user["id"], amount, int(time.time()), app_id))
            if not cur.rowcount: return api_error("Only accepted applications can have a commission record.", 409)
            commission_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return api_error("A commission has already been recorded for this application.", 409)
    return jsonify(id=commission_id, status="Pending"), 201


@app.patch("/api/commissions/<int:commission_id>")
def update_commission(commission_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("broker")
    if error: return error
    status = str(json_body().get("status", ""))
    if status not in ("Pending", "Paid", "Waived"): return api_error("Invalid commission status.", 400)
    with connect() as db:
        cur = db.execute("UPDATE commissions SET status=? WHERE id=? AND broker_id=?", (status, commission_id, user["id"]))
    if not cur.rowcount: return api_error("Commission record not found.", 404)
    return jsonify(status=status)


@app.get("/api/tickets")
def list_tickets():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    query = """SELECT t.*, p.title property_title, p.address, r.name renter_name, o.id owner_id
               FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id JOIN users r ON r.id=t.renter_id JOIN users o ON o.id=p.owner_id"""
    params = ()
    if user["role"] == "renter": query += " WHERE t.renter_id=?"; params = (user["id"],)
    elif user["role"] == "owner": query += " WHERE p.owner_id=?"; params = (user["id"],)
    query += " ORDER BY t.created_at DESC"
    with connect() as db: rows = db.execute(query, params).fetchall()
    return jsonify(tickets=[dict(row) for row in rows])


@app.post("/api/tickets")
def create_ticket():
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("renter")
    if error: return error
    body = json_body()
    try: property_id = int(body.get("property_id"))
    except (TypeError, ValueError): return api_error("Choose the property this issue is about.", 400)
    title, description = str(body.get("title", "")).strip(), str(body.get("description", "")).strip()
    category, priority = str(body.get("category", "Other")), str(body.get("priority", "Medium"))
    if not 3 <= len(title) <= 100 or not 5 <= len(description) <= 1000: return api_error("Check the issue title and description.", 400)
    if category not in ("Plumbing", "Electrical", "Appliance", "Structural", "Other") or priority not in ("Low", "Medium", "High", "Urgent"):
        return api_error("Choose a valid issue category and priority.", 400)
    with connect() as db:
        # A renter can only report on a property where their application was accepted.
        lives_there = db.execute("SELECT 1 FROM applications WHERE renter_id=? AND property_id=? AND status='Accepted'", (user["id"], property_id)).fetchone()
        if not lives_there: return api_error("Maintenance requests are available for your accepted rental only.", 403)
        now = int(time.time())
        cur = db.execute("INSERT INTO maintenance_tickets(property_id,renter_id,title,description,category,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (property_id,user["id"],title,description,category,priority,now,now))
    return jsonify(id=cur.lastrowid, status="Pending"), 201


@app.patch("/api/tickets/<int:ticket_id>")
def update_ticket(ticket_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("broker")
    if error: return error
    body = json_body()
    status = str(body.get("status", ""))
    note = str(body.get("manager_note", "")).strip()[:1000]
    if status not in ("Pending", "In Progress", "Resolved", "Skipped"): return api_error("Invalid ticket status.", 400)
    with connect() as db:
        cur = db.execute("UPDATE maintenance_tickets SET status=?,manager_note=?,updated_at=? WHERE id=?", (status,note,int(time.time()),ticket_id))
    if not cur.rowcount: return api_error("Ticket not found.", 404)
    return jsonify(status=status)


@app.post("/api/auth/logout")
def logout():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error
    raw_token = request.cookies.get("pm_session", "")
    if raw_token:
        with connect() as db:
            db.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (hashlib.sha256(raw_token.encode()).hexdigest(),))
    response = make_response(jsonify(status="signed_out"))
    response.delete_cookie("pm_session", path="/")
    token = secrets.token_urlsafe(32)
    response.set_cookie("pm_csrf", token, httponly=False, secure=COOKIE_SECURE,
                        samesite="Lax", path="/", max_age=60 * 60 * 24)
    response.set_data(jsonify(status="signed_out", csrfToken=token).get_data())
    return response


@app.cli.command("create-broker")
def create_broker():
    """Create a broker account interactively; never expose broker signup publicly."""
    email = input("Broker email: ").strip().lower()
    name = input("Broker name: ").strip()
    password = input("Broker password (12+ characters): ")
    if len(password) < 12 or "@" not in email:
        raise SystemExit("Provide a valid email and a password of at least 12 characters.")
    init_db()
    with connect() as db:
        db.execute("INSERT INTO users(email, name, role, password_hash, created_at) VALUES (?, ?, 'broker', ?, ?)",
                   (email, name, hasher.hash(password), int(time.time())))
    print("Broker account created.")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
