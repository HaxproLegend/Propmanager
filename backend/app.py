import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
import click
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import Flask, jsonify, make_response, request


ROOT = Path(__file__).resolve().parent.parent
DATABASE = Path(os.environ.get("DATABASE_PATH", ROOT / "backend" / "instance" / "propmanager.sqlite3"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
hasher = PasswordHasher()
DUMMY_PASSWORD_HASH = hasher.hash(secrets.token_urlsafe(32))


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
                property_type TEXT NOT NULL DEFAULT 'Apartment',
                address TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                monthly_rent INTEGER NOT NULL,
                bedrooms INTEGER NOT NULL DEFAULT 1,
                unit_count INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'Available',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
                renter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                message TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Pending',
                accepted_at INTEGER,
                ended_at INTEGER,
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
            CREATE TABLE IF NOT EXISTS commission_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                billing_period TEXT NOT NULL,
                party TEXT NOT NULL CHECK(party IN ('renter','owner')),
                rate_basis_points INTEGER NOT NULL DEFAULT 1000,
                amount_paise INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Paid','Waived')),
                created_at INTEGER NOT NULL,
                UNIQUE(application_id,billing_period,party)
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
            CREATE TABLE IF NOT EXISTS ticket_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL REFERENCES maintenance_tickets(id) ON DELETE CASCADE,
                actor_id INTEGER NOT NULL REFERENCES users(id),
                event_type TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                note TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_properties_owner_status ON properties(owner_id, status);
            CREATE INDEX IF NOT EXISTS idx_applications_renter_status ON applications(renter_id, status);
            CREATE INDEX IF NOT EXISTS idx_tickets_property_status ON maintenance_tickets(property_id, status);
            CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_time ON ticket_events(ticket_id, created_at);
        """)
        application_columns = {row[1] for row in db.execute("PRAGMA table_info(applications)")}
        property_columns = {row[1] for row in db.execute("PRAGMA table_info(properties)")}
        if "property_type" not in property_columns:
            db.execute("ALTER TABLE properties ADD COLUMN property_type TEXT NOT NULL DEFAULT 'Apartment'")
        if "unit_count" not in property_columns:
            db.execute("ALTER TABLE properties ADD COLUMN unit_count INTEGER NOT NULL DEFAULT 1")
        if "accepted_at" not in application_columns:
            db.execute("ALTER TABLE applications ADD COLUMN accepted_at INTEGER")
        if "ended_at" not in application_columns:
            db.execute("ALTER TABLE applications ADD COLUMN ended_at INTEGER")
        db.execute("UPDATE applications SET accepted_at=created_at WHERE status='Accepted' AND accepted_at IS NULL")
        db.execute("CREATE INDEX IF NOT EXISTS idx_commission_cycles_period_status ON commission_cycles(billing_period,status)")


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
            SELECT u.id, u.email, u.name, u.role, u.created_at
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
        old_token = request.cookies.get("pm_session", "")
        if old_token:
            old_hash = hashlib.sha256(old_token.encode()).hexdigest()
            db.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (old_hash,))
        db.execute("INSERT INTO auth_sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                   (hashlib.sha256(token.encode()).hexdigest(), user_id, now + 60 * 60 * 24 * 7, now))
    response.set_cookie("pm_session", token, httponly=True, secure=COOKIE_SECURE,
                        samesite="Lax", path="/", max_age=60 * 60 * 24 * 7)
    return set_csrf_cookie(response)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
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


@app.errorhandler(404)
def api_not_found(_error):
    if request.path.startswith("/api/"):
        return api_error("Endpoint not found.", 404)
    return _error


@app.errorhandler(405)
def api_method_not_allowed(_error):
    if request.path.startswith("/api/"):
        return api_error("Method not allowed.", 405)
    return _error


@app.errorhandler(413)
def request_too_large(_error):
    return api_error("Request is too large.", 413)


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
    response = make_response(jsonify(user={"id": user_id, "email": email, "name": name, "role": role, "created_at": int(time.time())}), 201)
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
        user = db.execute("SELECT id, email, name, role, password_hash, created_at FROM users WHERE email = ?", (email,)).fetchone()
        valid = False
        try:
            valid = hasher.verify(user["password_hash"] if user else DUMMY_PASSWORD_HASH, password)
        except (VerifyMismatchError, InvalidHashError):
            valid = False
        valid = bool(user) and valid
        if not valid:
            started = attempt["window_started"] if attempt and now - attempt["window_started"] < 900 else now
            count = (attempt["failed_count"] + 1) if attempt and started == attempt["window_started"] else 1
            locked_until = now + 900 if count >= 5 else 0
            db.execute("INSERT INTO login_attempts(email, failed_count, window_started, locked_until) VALUES (?, ?, ?, ?) "
                       "ON CONFLICT(email) DO UPDATE SET failed_count=excluded.failed_count, window_started=excluded.window_started, locked_until=excluded.locked_until",
                       (email, count, started, locked_until))
            return api_error("Unable to sign in with those details.", 401)
        db.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
        public_user = {key: user[key] for key in ("id", "email", "name", "role", "created_at")}
    response = make_response(jsonify(user=public_user))
    return issue_session(response, public_user["id"])


@app.get("/api/auth/me")
def me():
    user = current_user()
    if not user:
        return api_error("Sign in to continue.", 401)
    return jsonify(user=user)


@app.patch("/api/auth/me")
def update_me():
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user = current_user()
    if not user: return api_error("Sign in to continue.", 401)
    name = str(json_body().get("name", "")).strip()
    if not 2 <= len(name) <= 80: return api_error("Name must be between 2 and 80 characters.", 400)
    with connect() as db:
        db.execute("UPDATE users SET name=? WHERE id=?", (name,user["id"]))
    updated = current_user()
    return jsonify(user=updated)


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
    property_type = str(body.get("property_type", "Apartment"))
    description = str(body.get("description", "")).strip()[:1000]
    try: rent, unit_count = int(body.get("monthly_rent")), int(body.get("unit_count", body.get("bedrooms", 1)))
    except (TypeError, ValueError): return api_error("Enter a valid rent and unit/room count.", 400)
    if not 3 <= len(title) <= 100 or not 5 <= len(address) <= 240 or rent < 1 or not 1 <= unit_count <= 500 or property_type not in ("Apartment", "PG/Hostel", "Office/Commercial"):
        return api_error("Check the listing details and try again.", 400)
    with connect() as db:
        cur = db.execute("INSERT INTO properties(owner_id,title,property_type,address,description,monthly_rent,bedrooms,unit_count,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (user["id"], title, property_type, address, description, rent, unit_count, unit_count, int(time.time())))
        row = db.execute("SELECT p.*, u.name owner_name FROM properties p JOIN users u ON u.id=p.owner_id WHERE p.id=?", (cur.lastrowid,)).fetchone()
    return jsonify(property=dict(row)), 201


@app.patch("/api/properties/<int:property_id>")
def update_property(property_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner")
    if error: return error
    body = json_body()
    title, address = str(body.get("title", "")).strip(), str(body.get("address", "")).strip()
    property_type = str(body.get("property_type", "Apartment"))
    description = str(body.get("description", "")).strip()[:1000]
    try: rent, unit_count = int(body.get("monthly_rent")), int(body.get("unit_count", body.get("bedrooms", 1)))
    except (TypeError, ValueError): return api_error("Enter a valid rent and unit/room count.", 400)
    status = str(body.get("status", "Available"))
    if not 3 <= len(title) <= 100 or not 5 <= len(address) <= 240 or rent < 1 or not 1 <= unit_count <= 500 or property_type not in ("Apartment", "PG/Hostel", "Office/Commercial"):
        return api_error("Check the listing details and try again.", 400)
    if status not in ("Available", "Unavailable"): return api_error("A listing can only be set to available or unavailable.", 400)
    with connect() as db:
        cur = db.execute("UPDATE properties SET title=?,property_type=?,address=?,description=?,monthly_rent=?,bedrooms=?,unit_count=?,status=? WHERE id=? AND owner_id=? AND status!='Rented'", (title,property_type,address,description,rent,unit_count,unit_count,status,property_id,user["id"]))
        if not cur.rowcount: return api_error("Listing not found or already rented.", 404)
        row = db.execute("SELECT p.*,u.name owner_name FROM properties p JOIN users u ON u.id=p.owner_id WHERE p.id=?", (property_id,)).fetchone()
    return jsonify(property=dict(row))


@app.get("/api/dashboard")
def dashboard_summary():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        if user["role"] == "renter":
            summary = {
                "available_properties": db.execute("SELECT COUNT(*) FROM properties WHERE status='Available'").fetchone()[0],
                "applications": db.execute("SELECT COUNT(*) FROM applications WHERE renter_id=?", (user["id"],)).fetchone()[0],
                "open_tickets": db.execute("SELECT COUNT(*) FROM maintenance_tickets WHERE renter_id=? AND status NOT IN ('Resolved','Skipped')", (user["id"],)).fetchone()[0],
            }
        elif user["role"] == "owner":
            summary = {
                "listings": db.execute("SELECT COUNT(*) FROM properties WHERE owner_id=?", (user["id"],)).fetchone()[0],
                "pending_applications": db.execute("SELECT COUNT(*) FROM applications a JOIN properties p ON p.id=a.property_id WHERE p.owner_id=? AND a.status='Pending'", (user["id"],)).fetchone()[0],
                "open_tickets": db.execute("SELECT COUNT(*) FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id WHERE p.owner_id=? AND t.status NOT IN ('Resolved','Skipped')", (user["id"],)).fetchone()[0],
            }
        else:
            summary = {
                "pending_applications": db.execute("SELECT COUNT(*) FROM applications WHERE status='Pending'").fetchone()[0],
                "in_progress_tickets": db.execute("SELECT COUNT(*) FROM maintenance_tickets WHERE status='In Progress'").fetchone()[0],
                "pending_commission_amount_paise": db.execute("SELECT COALESCE(SUM(amount_paise),0) FROM commission_cycles WHERE status='Pending'").fetchone()[0],
                "skipped_tickets": db.execute("SELECT COUNT(*) FROM maintenance_tickets WHERE status='Skipped'").fetchone()[0],
            }
    return jsonify(role=user["role"], summary=summary)


@app.get("/api/applications")
def list_applications():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    query = """SELECT a.*, p.title property_title, p.property_type, p.address, p.monthly_rent, r.name renter_name, r.email renter_email, o.name owner_name
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
        now = int(time.time())
        cur = db.execute("UPDATE applications SET status=?,accepted_at=? WHERE id=? AND status='Pending' AND property_id IN (SELECT id FROM properties WHERE owner_id=? AND (?='Declined' OR status='Available'))", (status, now if status == "Accepted" else None, application_id, user["id"], status))
        if not cur.rowcount: return api_error("Application not found or already decided.", 404)
        if status == "Accepted": db.execute("UPDATE properties SET status='Rented' WHERE id=(SELECT property_id FROM applications WHERE id=?)", (application_id,))
    if status == "Accepted":
        generate_commission_cycles(datetime.now(timezone.utc).strftime("%Y-%m"), application_id)
    return jsonify(status=status)


def generate_commission_cycles(billing_period, application_id=None):
    try:
        start = datetime.strptime(billing_period, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("Billing period must use YYYY-MM format.")
    if start.strftime("%Y-%m") != billing_period:
        raise ValueError("Billing period must use YYYY-MM format.")
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    start_ts, end_ts, now = int(start.timestamp()), int(end.timestamp()), int(time.time())
    query = """SELECT a.id,p.monthly_rent FROM applications a JOIN properties p ON p.id=a.property_id
               WHERE a.status IN ('Accepted','Ended') AND a.accepted_at < ?
               AND (a.ended_at IS NULL OR a.ended_at > ?)"""
    params = [end_ts, start_ts]
    if application_id is not None:
        query += " AND a.id=?"
        params.append(application_id)
    with connect() as db:
        eligible = db.execute(query, params).fetchall()
        created = 0
        for application in eligible:
            # Store INR cents (paise); 1,000 basis points is 10% of monthly rent.
            amount_paise = (application["monthly_rent"] * 100 * 1000) // 10000
            for party in ("renter", "owner"):
                cursor = db.execute("""INSERT OR IGNORE INTO commission_cycles
                    (application_id,billing_period,party,rate_basis_points,amount_paise,status,created_at)
                    VALUES(?,?,?,?,?,'Pending',?)""", (application["id"],billing_period,party,1000,amount_paise,now))
                created += cursor.rowcount
    return created


@app.post("/api/applications/<int:application_id>/end")
def end_rental(application_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user = current_user()
    if not user: return api_error("Sign in to continue.", 401)
    if user["role"] not in ("owner", "broker"): return api_error("You don't have access to this action.", 403)
    body = json_body()
    reason = str(body.get("reason", "")).strip()[:500]
    with connect() as db:
        rental = db.execute("""SELECT a.property_id FROM applications a JOIN properties p ON p.id=a.property_id
                              WHERE a.id=? AND a.status='Accepted' AND (?='broker' OR p.owner_id=?)""", (application_id,user["role"],user["id"])).fetchone()
        if not rental: return api_error("Active rental not found.", 404)
        now = int(time.time())
        db.execute("UPDATE applications SET status='Ended',ended_at=? WHERE id=?", (now,application_id))
        db.execute("UPDATE properties SET status='Available' WHERE id=?", (rental["property_id"],))
    return jsonify(status="Ended", ended_at=now, reason=reason)


@app.get("/api/commissions")
def list_commissions():
    user, error = need_role("broker")
    if error: return error
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    generate_commission_cycles(period)
    with connect() as db:
        rows = db.execute("""SELECT c.*, a.status application_status, p.title property_title, p.monthly_rent,
                            r.name renter_name, o.name owner_name
                            FROM commission_cycles c JOIN applications a ON a.id=c.application_id JOIN properties p ON p.id=a.property_id
                            JOIN users r ON r.id=a.renter_id JOIN users o ON o.id=p.owner_id
                            ORDER BY c.billing_period DESC,c.created_at DESC,c.party""").fetchall()
    return jsonify(commissions=[dict(row) for row in rows], billing_period=period, rate_basis_points=1000)


@app.post("/api/commissions/generate")
def generate_commissions_route():
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("broker")
    if error: return error
    billing_period = str(json_body().get("billing_period", ""))
    try:
        created = generate_commission_cycles(billing_period)
    except ValueError as exc:
        return api_error(str(exc), 400)
    return jsonify(billing_period=billing_period, created=created, message="Monthly charges are created idempotently for the renter and owner."), 201


@app.patch("/api/commissions/<int:commission_id>")
def update_commission(commission_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("broker")
    if error: return error
    status = str(json_body().get("status", ""))
    if status not in ("Pending", "Paid", "Waived"): return api_error("Invalid commission status.", 400)
    with connect() as db:
        cur = db.execute("UPDATE commission_cycles SET status=? WHERE id=?", (status, commission_id))
    if not cur.rowcount: return api_error("Commission record not found.", 404)
    return jsonify(status=status)


@app.get("/api/tickets")
def list_tickets():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    query = """SELECT t.*, p.title property_title, p.address, r.name renter_name, o.id owner_id,
               (SELECT COUNT(*) FROM maintenance_tickets similar WHERE similar.id != t.id
                AND similar.property_id=t.property_id AND similar.category=t.category
                AND similar.status NOT IN ('Resolved','Skipped')) AS similar_issue_count
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
    if category not in ("Maintenance", "Plumbing", "Electrical", "Appliance", "Structural", "Personal safety", "Neighbourhood safety", "Security/access", "Cleanliness/facilities", "Other") or priority not in ("Low", "Medium", "High", "Urgent"):
        return api_error("Choose a valid issue category and priority.", 400)
    with connect() as db:
        # A renter can only report on a property where their application was accepted.
        lives_there = db.execute("SELECT 1 FROM applications WHERE renter_id=? AND property_id=? AND status='Accepted'", (user["id"], property_id)).fetchone()
        if not lives_there: return api_error("Maintenance requests are available for your accepted rental only.", 403)
        now = int(time.time())
        cur = db.execute("INSERT INTO maintenance_tickets(property_id,renter_id,title,description,category,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (property_id,user["id"],title,description,category,priority,now,now))
        db.execute("INSERT INTO ticket_events(ticket_id,actor_id,event_type,new_status,note,created_at) VALUES(?,?,'created','Pending',?,?)", (cur.lastrowid,user["id"],title,now))
    return jsonify(id=cur.lastrowid, status="Pending"), 201


@app.get("/api/tickets/<int:ticket_id>")
def get_ticket(ticket_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        row = db.execute("""SELECT t.*,p.title property_title,p.address,r.name renter_name,p.owner_id,
                           (SELECT COUNT(*) FROM maintenance_tickets s WHERE s.id!=t.id AND s.property_id=t.property_id
                            AND s.category=t.category AND s.status NOT IN ('Resolved','Skipped')) AS similar_issue_count
                           FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id JOIN users r ON r.id=t.renter_id
                           WHERE t.id=?""", (ticket_id,)).fetchone()
        if not row: return api_error("Ticket not found.", 404)
        if user["role"] == "renter" and row["renter_id"] != user["id"]: return api_error("Ticket not found.", 404)
        if user["role"] == "owner" and row["owner_id"] != user["id"]: return api_error("Ticket not found.", 404)
        events = db.execute("SELECT e.id,e.event_type,e.old_status,e.new_status,e.note,e.created_at,u.name actor_name FROM ticket_events e JOIN users u ON u.id=e.actor_id WHERE e.ticket_id=? ORDER BY e.created_at,e.id", (ticket_id,)).fetchall()
    return jsonify(ticket=dict(row), history=[dict(event) for event in events])


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
        existing = db.execute("SELECT status,manager_note FROM maintenance_tickets WHERE id=?", (ticket_id,)).fetchone()
        if not existing: return api_error("Ticket not found.", 404)
        now = int(time.time())
        cur = db.execute("UPDATE maintenance_tickets SET status=?,manager_note=?,updated_at=? WHERE id=?", (status,note,now,ticket_id))
        if existing["status"] != status or existing["manager_note"] != note:
            event_type = "status_changed" if existing["status"] != status else "note_updated"
            db.execute("INSERT INTO ticket_events(ticket_id,actor_id,event_type,old_status,new_status,note,created_at) VALUES(?,?,?,?,?,?,?)", (ticket_id,user["id"],event_type,existing["status"],status,note,now))
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


@app.cli.command("generate-commissions")
@click.option("--month", default=lambda: datetime.now(timezone.utc).strftime("%Y-%m"), help="Billing month in YYYY-MM format.")
def generate_commissions_command(month):
    """Generate the two recurring 10% ledger charges for active rentals."""
    init_db()
    try:
        count = generate_commission_cycles(month)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Generated {count} commission entries for {month}.")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
