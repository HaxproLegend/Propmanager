import csv
import hashlib
import hmac
import io
import os
import re
import secrets
import shutil
import sqlite3
import time
from datetime import datetime, timedelta, timezone
import click
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import Flask, Response, jsonify, make_response, request


ROOT = Path(__file__).resolve().parent.parent
DATABASE = Path(os.environ.get("DATABASE_PATH", ROOT / "backend" / "instance" / "propmanager.sqlite3"))
# Secure cookies are the safe default for hosted deployments. Local HTTP
# development must opt out explicitly with COOKIE_SECURE=false.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
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
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS org_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('org_admin','manager','broker','accountant','technician')),
                created_at INTEGER NOT NULL,
                UNIQUE(org_id,user_id)
            );
            CREATE TABLE IF NOT EXISTS org_invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                email TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('org_admin','manager','broker','accountant','technician')),
                token_hash TEXT NOT NULL UNIQUE,
                expires_at INTEGER NOT NULL,
                accepted_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL,
                UNIQUE(org_id,email)
            );
            CREATE TABLE IF NOT EXISTS commission_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                party TEXT NOT NULL CHECK(party IN ('renter','owner')),
                rate_basis_points INTEGER NOT NULL DEFAULT 1000 CHECK(rate_basis_points BETWEEN 0 AND 10000),
                effective_from INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(org_id,party,effective_from)
            );
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'Manual',
                status TEXT NOT NULL DEFAULT 'New' CHECK(status IN ('New','Contacted','Qualified','Converted','Lost')),
                notes TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
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
                org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL,
                image_url TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
                unit_label TEXT NOT NULL,
                monthly_rent INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available','Rented')),
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
                renter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                message TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Pending',
                decline_reason TEXT NOT NULL DEFAULT '',
                unit_id INTEGER REFERENCES units(id) ON DELETE SET NULL,
                accepted_at INTEGER,
                ended_at INTEGER,
                created_at INTEGER NOT NULL,
                UNIQUE(property_id, renter_id)
            );
            CREATE TABLE IF NOT EXISTS application_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                actor_id INTEGER NOT NULL REFERENCES users(id),
                event_type TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                note TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                link TEXT NOT NULL DEFAULT '',
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS demo_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
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
            CREATE INDEX IF NOT EXISTS idx_units_property_status ON units(property_id, status);
            CREATE INDEX IF NOT EXISTS idx_app_events_application_time ON application_events(application_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read, created_at);
            CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id, org_id);
            CREATE INDEX IF NOT EXISTS idx_leads_org_status ON leads(org_id, status);
            CREATE INDEX IF NOT EXISTS idx_terms_org_party ON commission_terms(org_id, party, effective_from);
        """)
        application_columns = {row[1] for row in db.execute("PRAGMA table_info(applications)")}
        property_columns = {row[1] for row in db.execute("PRAGMA table_info(properties)")}
        if "property_type" not in property_columns:
            db.execute("ALTER TABLE properties ADD COLUMN property_type TEXT NOT NULL DEFAULT 'Apartment'")
        if "unit_count" not in property_columns:
            db.execute("ALTER TABLE properties ADD COLUMN unit_count INTEGER NOT NULL DEFAULT 1")
        if "image_url" not in property_columns:
            db.execute("ALTER TABLE properties ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
        if "org_id" not in property_columns:
            db.execute("ALTER TABLE properties ADD COLUMN org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL")
        if "accepted_at" not in application_columns:
            db.execute("ALTER TABLE applications ADD COLUMN accepted_at INTEGER")
        if "ended_at" not in application_columns:
            db.execute("ALTER TABLE applications ADD COLUMN ended_at INTEGER")
        if "unit_id" not in application_columns:
            db.execute("ALTER TABLE applications ADD COLUMN unit_id INTEGER REFERENCES units(id) ON DELETE SET NULL")
        if "decline_reason" not in application_columns:
            # Re-check: another process may have applied this migration already.
            current_columns = {row[1] for row in db.execute("PRAGMA table_info(applications)")}
            if "decline_reason" not in current_columns:
                db.execute("ALTER TABLE applications ADD COLUMN decline_reason TEXT NOT NULL DEFAULT ''")
        db.execute("UPDATE applications SET accepted_at=created_at WHERE status='Accepted' AND accepted_at IS NULL")

        # Backfill one unit per declared unit/room. Existing records are preserved.
        now = int(time.time())
        for prop in db.execute("SELECT id, monthly_rent, unit_count FROM properties").fetchall():
            existing = db.execute("SELECT COUNT(*) FROM units WHERE property_id=?", (prop["id"],)).fetchone()[0]
            for number in range(existing + 1, max(prop["unit_count"], 1) + 1):
                db.execute("INSERT INTO units(property_id,unit_label,monthly_rent,status,created_at) VALUES(?,?,?,'Available',?)",
                           (prop["id"], f"Unit {number}", prop["monthly_rent"], now))

        # Attach accepted applications to a unit and mark it rented.
        for application in db.execute("SELECT id, property_id FROM applications WHERE status='Accepted' AND unit_id IS NULL").fetchall():
            unit = db.execute("SELECT id FROM units WHERE property_id=? AND status='Available' ORDER BY id LIMIT 1", (application["property_id"],)).fetchone()
            if unit:
                db.execute("UPDATE applications SET unit_id=? WHERE id=?", (unit["id"], application["id"]))
                db.execute("UPDATE units SET status='Rented' WHERE id=?", (unit["id"],))

        db.execute("CREATE INDEX IF NOT EXISTS idx_commission_cycles_period_status ON commission_cycles(billing_period,status)")


def api_error(message, status):
    return jsonify(error=message), status


def record_application_event(db, application_id, actor_id, event_type, old_status, new_status, note="", at=None):
    db.execute("""INSERT INTO application_events(application_id,actor_id,event_type,old_status,new_status,note,created_at)
                  VALUES(?,?,?,?,?,?,?)""",
               (application_id, actor_id, event_type, old_status, new_status, note, at or int(time.time())))


def notify(db, user_id, kind, title, body="", link="", at=None):
    db.execute("""INSERT INTO notifications(user_id,type,title,body,link,created_at)
                  VALUES(?,?,?,?,?,?)""",
               (user_id, kind, title, body, link, at or int(time.time())))


def valid_image_url(value):
    value = str(value or "").strip()[:500]
    if value and not value.lower().startswith(("http://", "https://")):
        return None
    return value


ORG_ROLES = ("org_admin", "manager", "broker", "accountant", "technician")


def org_role(db, org_id, user):
    if not user:
        return None
    if user["role"] == "broker":
        return "broker"  # global operator can serve every organization
    row = db.execute("SELECT role FROM org_members WHERE org_id=? AND user_id=?", (org_id, user["id"])).fetchone()
    return row["role"] if row else None


def require_org(db, org_id, user, roles=ORG_ROLES):
    role = org_role(db, org_id, user)
    if not role:
        return None, api_error("You are not a member of this organization.", 403)
    if role not in roles:
        return None, api_error("Your organization role cannot perform this action.", 403)
    return role, None


def org_slug(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]
    return slug or "organization"


def csv_cell(value):
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def csv_response(rows, filename):
    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow([csv_cell(value) for value in row])
    return Response(output.getvalue(), content_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


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
    query = """SELECT p.*, u.name owner_name,
               (SELECT COUNT(*) FROM units un WHERE un.property_id=p.id AND un.status='Available') AS available_units
               FROM properties p JOIN users u ON u.id=p.owner_id WHERE 1=1"""
    params = []
    if user and user["role"] == "owner":
        query += " AND p.owner_id=?"
        params.append(user["id"])
    elif not (user and user["role"] == "broker"):
        query += " AND p.status='Available'"

    search = request.args.get("q", "").strip()[:100]
    location = request.args.get("location", "").strip()[:100]
    property_type = request.args.get("property_type", "").strip()
    status = request.args.get("status", "").strip()
    try:
        min_rent = int(request.args["min_rent"]) if request.args.get("min_rent") else None
        max_rent = int(request.args["max_rent"]) if request.args.get("max_rent") else None
    except (TypeError, ValueError):
        return api_error("Enter valid rent limits.", 400)
    if (min_rent is not None and min_rent < 0) or (max_rent is not None and max_rent < 0) or \
       (min_rent is not None and max_rent is not None and min_rent > max_rent):
        return api_error("Enter valid rent limits.", 400)
    if property_type and property_type not in ("Apartment", "PG/Hostel", "Office/Commercial"):
        return api_error("Choose a valid property type.", 400)
    if status and status not in ("Available", "Unavailable", "Rented"):
        return api_error("Choose a valid listing status.", 400)

    if search:
        query += " AND (LOWER(p.title) LIKE ? OR LOWER(p.description) LIKE ?)"
        params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])
    if location:
        query += " AND LOWER(p.address) LIKE ?"
        params.append(f"%{location.lower()}%")
    if property_type:
        query += " AND p.property_type=?"
        params.append(property_type)
    if status:
        query += " AND p.status=?"
        params.append(status)
    if min_rent is not None:
        query += " AND p.monthly_rent>=?"
        params.append(min_rent)
    if max_rent is not None:
        query += " AND p.monthly_rent<=?"
        params.append(max_rent)
    query += " ORDER BY p.created_at DESC"
    with connect() as db:
        rows = db.execute(query, params).fetchall()
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
    image_url = valid_image_url(body.get("image_url", ""))
    try: rent, unit_count = int(body.get("monthly_rent")), int(body.get("unit_count", body.get("bedrooms", 1)))
    except (TypeError, ValueError): return api_error("Enter a valid rent and unit/room count.", 400)
    if image_url is None: return api_error("Enter a valid image URL.", 400)
    if not 3 <= len(title) <= 100 or not 5 <= len(address) <= 240 or rent < 1 or not 1 <= unit_count <= 500 or property_type not in ("Apartment", "PG/Hostel", "Office/Commercial"):
        return api_error("Check the listing details and try again.", 400)
    with connect() as db:
        now = int(time.time())
        cur = db.execute("INSERT INTO properties(owner_id,title,property_type,address,description,monthly_rent,bedrooms,unit_count,image_url,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (user["id"], title, property_type, address, description, rent, unit_count, unit_count, image_url, now))
        property_id = cur.lastrowid
        for number in range(1, unit_count + 1):
            db.execute("INSERT INTO units(property_id,unit_label,monthly_rent,status,created_at) VALUES(?,?,?,'Available',?)",
                       (property_id, f"Unit {number}", rent, now))
        row = db.execute("SELECT p.*, u.name owner_name FROM properties p JOIN users u ON u.id=p.owner_id WHERE p.id=?", (property_id,)).fetchone()
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
    image_url = valid_image_url(body.get("image_url", ""))
    try: rent, unit_count = int(body.get("monthly_rent")), int(body.get("unit_count", body.get("bedrooms", 1)))
    except (TypeError, ValueError): return api_error("Enter a valid rent and unit/room count.", 400)
    status = str(body.get("status", "Available"))
    if image_url is None: return api_error("Enter a valid image URL.", 400)
    if not 3 <= len(title) <= 100 or not 5 <= len(address) <= 240 or rent < 1 or not 1 <= unit_count <= 500 or property_type not in ("Apartment", "PG/Hostel", "Office/Commercial"):
        return api_error("Check the listing details and try again.", 400)
    if status not in ("Available", "Unavailable"): return api_error("A listing can only be set to available or unavailable.", 400)
    with connect() as db:
        cur = db.execute("UPDATE properties SET title=?,property_type=?,address=?,description=?,monthly_rent=?,bedrooms=?,unit_count=?,image_url=?,status=? WHERE id=? AND owner_id=? AND status!='Rented'", (title,property_type,address,description,rent,unit_count,unit_count,image_url,status,property_id,user["id"]))
        if not cur.rowcount: return api_error("Listing not found or already rented.", 404)
        now = int(time.time())
        current_units = db.execute("SELECT COUNT(*) FROM units WHERE property_id=?", (property_id,)).fetchone()[0]
        for number in range(current_units + 1, unit_count + 1):
            db.execute("INSERT INTO units(property_id,unit_label,monthly_rent,status,created_at) VALUES(?,?,?,'Available',?)",
                       (property_id, f"Unit {number}", rent, now))
        db.execute("UPDATE units SET monthly_rent=? WHERE property_id=? AND status='Available'", (rent, property_id))
        row = db.execute("SELECT p.*,u.name owner_name FROM properties p JOIN users u ON u.id=p.owner_id WHERE p.id=?", (property_id,)).fetchone()
    return jsonify(property=dict(row))


@app.get("/api/properties/<int:property_id>/units")
def list_units(property_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        prop = db.execute("SELECT id,owner_id,status FROM properties WHERE id=?", (property_id,)).fetchone()
        if not prop: return api_error("Listing not found.", 404)
        if user["role"] == "owner" and prop["owner_id"] != user["id"]: return api_error("Listing not found.", 404)
        rows = db.execute("SELECT id,unit_label,monthly_rent,status FROM units WHERE property_id=? ORDER BY id", (property_id,)).fetchall()
    return jsonify(units=[dict(row) for row in rows])


@app.post("/api/properties/<int:property_id>/units")
def add_unit(property_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner")
    if error: return error
    body = json_body()
    unit_label = str(body.get("unit_label", "")).strip()[:60]
    try: rent = int(body.get("monthly_rent"))
    except (TypeError, ValueError): return api_error("Enter a valid unit rent.", 400)
    if not 1 <= len(unit_label) <= 60 or rent < 1: return api_error("Check the unit details.", 400)
    with connect() as db:
        prop = db.execute("SELECT id,unit_count FROM properties WHERE id=? AND owner_id=?", (property_id, user["id"])).fetchone()
        if not prop: return api_error("Listing not found.", 404)
        db.execute("INSERT INTO units(property_id,unit_label,monthly_rent,status,created_at) VALUES(?,?,?,'Available',?)",
                   (property_id, unit_label, rent, int(time.time())))
        db.execute("UPDATE properties SET unit_count=unit_count+1 WHERE id=?", (property_id,))
        row = db.execute("SELECT id,unit_label,monthly_rent,status FROM units WHERE id=?", (db.execute("SELECT last_insert_rowid()").fetchone()[0],)).fetchone()
    return jsonify(unit=dict(row)), 201


@app.get("/api/orgs")
def list_orgs():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        if user["role"] == "broker":
            rows = db.execute("SELECT o.* FROM organizations o ORDER BY o.created_at DESC").fetchall()
        else:
            rows = db.execute("""SELECT o.*, m.role member_role FROM organizations o
                                 JOIN org_members m ON m.org_id=o.id WHERE m.user_id=?
                                 ORDER BY o.created_at DESC""", (user["id"],)).fetchall()
    return jsonify(organizations=[dict(row) for row in rows])


@app.post("/api/orgs")
def create_org():
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    body = json_body()
    name = str(body.get("name", "")).strip()
    slug = org_slug(str(body.get("slug", "")).strip() or name)
    if not 3 <= len(name) <= 80 or not re.fullmatch(r"[a-z0-9-]{3,60}", slug):
        return api_error("Enter an organization name and a valid slug.", 400)
    try:
        with connect() as db:
            now = int(time.time())
            cursor = db.execute("INSERT INTO organizations(name,slug,created_by,created_at) VALUES(?,?,?,?)",
                                (name, slug, user["id"], now))
            org_id = cursor.lastrowid
            db.execute("INSERT INTO org_members(org_id,user_id,role,created_at) VALUES(?,?,'org_admin',?)",
                       (org_id, user["id"], now))
            row = db.execute("SELECT o.*, 'org_admin' member_role FROM organizations o WHERE o.id=?", (org_id,)).fetchone()
    except sqlite3.IntegrityError:
        return api_error("An organization with that slug already exists.", 409)
    return jsonify(organization=dict(row)), 201


@app.get("/api/orgs/<int:org_id>")
def get_org(org_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        role, error = require_org(db, org_id, user)
        if error: return error
        org = db.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
        if not org: return api_error("Organization not found.", 404)
        result = dict(org)
        result["member_role"] = role
    return jsonify(organization=result)


@app.patch("/api/orgs/<int:org_id>")
def update_org(org_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    body = json_body()
    name = str(body.get("name", "")).strip()
    slug = org_slug(str(body.get("slug", "")).strip() or name)
    if not 3 <= len(name) <= 80 or not re.fullmatch(r"[a-z0-9-]{3,60}", slug):
        return api_error("Enter an organization name and a valid slug.", 400)
    with connect() as db:
        _, error = require_org(db, org_id, user, ("org_admin", "broker"))
        if error: return error
        try:
            db.execute("UPDATE organizations SET name=?,slug=? WHERE id=?", (name, slug, org_id))
        except sqlite3.IntegrityError:
            return api_error("An organization with that slug already exists.", 409)
        row = db.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
    return jsonify(organization=dict(row))


@app.get("/api/orgs/<int:org_id>/members")
def list_members(org_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        _, error = require_org(db, org_id, user)
        if error: return error
        rows = db.execute("""SELECT m.id,m.role,m.created_at,u.id user_id,u.name,u.email,u.role account_role
                             FROM org_members m JOIN users u ON u.id=m.user_id WHERE m.org_id=?
                             ORDER BY m.created_at DESC""", (org_id,)).fetchall()
    return jsonify(members=[dict(row) for row in rows])


@app.patch("/api/orgs/<int:org_id>/members/<int:user_id>")
def update_member(org_id, user_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    role = str(json_body().get("role", ""))
    if role not in ORG_ROLES: return api_error("Choose a valid organization role.", 400)
    with connect() as db:
        _, error = require_org(db, org_id, user, ("org_admin", "broker"))
        if error: return error
        cur = db.execute("UPDATE org_members SET role=? WHERE org_id=? AND user_id=?", (role, org_id, user_id))
        if not cur.rowcount: return api_error("Member not found.", 404)
    return jsonify(role=role)


@app.delete("/api/orgs/<int:org_id>/members/<int:user_id>")
def remove_member(org_id, user_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    with connect() as db:
        _, error = require_org(db, org_id, user, ("org_admin", "broker"))
        if error: return error
        cur = db.execute("DELETE FROM org_members WHERE org_id=? AND user_id=?", (org_id, user_id))
        if not cur.rowcount: return api_error("Member not found.", 404)
    return jsonify(status="removed")


@app.get("/api/orgs/<int:org_id>/invitations")
def list_invitations(org_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        _, error = require_org(db, org_id, user)
        if error: return error
        rows = db.execute("SELECT id,email,role,expires_at,accepted_by,created_at FROM org_invitations WHERE org_id=? ORDER BY created_at DESC", (org_id,)).fetchall()
    return jsonify(invitations=[dict(row) for row in rows])


@app.post("/api/orgs/<int:org_id>/invitations")
def invite_member(org_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    body = json_body()
    email = str(body.get("email", "")).strip().lower()
    role = str(body.get("role", "manager"))
    if len(email) > 254 or "@" not in email or role not in ORG_ROLES:
        return api_error("Enter a valid email and organization role.", 400)
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with connect() as db:
        _, error = require_org(db, org_id, user, ("org_admin", "broker"))
        if error: return error
        db.execute("""INSERT INTO org_invitations(org_id,email,role,token_hash,expires_at,accepted_by,created_at)
                      VALUES(?,?,?,?,?,NULL,?)
                      ON CONFLICT(org_id,email) DO UPDATE SET role=excluded.role,token_hash=excluded.token_hash,
                      expires_at=excluded.expires_at,accepted_by=NULL,created_at=excluded.created_at""",
                   (org_id, email, role, hashlib.sha256(token.encode()).hexdigest(), now + 7 * 86400, now))
    return jsonify(email=email, role=role, token=token, expires_at=now + 7 * 86400), 201


@app.post("/api/orgs/invitations/<token>/accept")
def accept_invitation(token):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = int(time.time())
    with connect() as db:
        invite = db.execute("SELECT * FROM org_invitations WHERE token_hash=? AND expires_at>? AND accepted_by IS NULL",
                            (token_hash, now)).fetchone()
        if not invite: return api_error("This invitation is invalid or has expired.", 404)
        if invite["email"].lower() != user["email"].lower():
            return api_error("Sign in with the invited email address to accept.", 403)
        db.execute("INSERT OR IGNORE INTO org_members(org_id,user_id,role,created_at) VALUES(?,?,?,?)",
                   (invite["org_id"], user["id"], invite["role"], now))
        db.execute("UPDATE org_invitations SET accepted_by=? WHERE id=?", (user["id"], invite["id"]))
        org = db.execute("SELECT id,name,slug FROM organizations WHERE id=?", (invite["org_id"],)).fetchone()
    return jsonify(organization=dict(org), role=invite["role"])


@app.post("/api/orgs/<int:org_id>/properties/<int:property_id>")
def assign_property(org_id, property_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    with connect() as db:
        prop = db.execute("SELECT id,owner_id,title FROM properties WHERE id=?", (property_id,)).fetchone()
        if not prop: return api_error("Listing not found.", 404)
        if user["role"] != "broker":
            _, error = require_org(db, org_id, user)
            if error: return error
            if prop["owner_id"] != user["id"]:
                return api_error("You can only link your own listings.", 403)
        db.execute("UPDATE properties SET org_id=? WHERE id=?", (org_id, property_id))
    return jsonify(status="linked", property_id=property_id, title=prop["title"])


@app.delete("/api/orgs/<int:org_id>/properties/<int:property_id>")
def unassign_property(org_id, property_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    with connect() as db:
        _, error = require_org(db, org_id, user, ("org_admin", "broker"))
        if error: return error
        db.execute("UPDATE properties SET org_id=NULL WHERE id=? AND org_id=?", (property_id, org_id))
    return jsonify(status="unlinked")


@app.get("/api/orgs/<int:org_id>/commission-terms")
def list_commission_terms(org_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        _, error = require_org(db, org_id, user)
        if error: return error
        rows = db.execute("SELECT * FROM commission_terms WHERE org_id=? ORDER BY effective_from DESC,id DESC", (org_id,)).fetchall()
    return jsonify(terms=[dict(row) for row in rows])


@app.post("/api/orgs/<int:org_id>/commission-terms")
def set_commission_term(org_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    body = json_body()
    party = str(body.get("party", ""))
    if party not in ("renter", "owner"): return api_error("Choose renter or owner.", 400)
    try: rate = int(body.get("rate_basis_points"))
    except (TypeError, ValueError): return api_error("Enter a rate in basis points.", 400)
    if not 0 <= rate <= 10000: return api_error("Rate must be between 0 and 10000 basis points.", 400)
    effective = str(body.get("effective_from", ""))
    try:
        effective_from = int(datetime.strptime(effective, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) if effective else int(time.time())
    except ValueError:
        return api_error("Use YYYY-MM-DD for the effective date.", 400)
    with connect() as db:
        _, error = require_org(db, org_id, user, ("org_admin", "broker"))
        if error: return error
        db.execute("""INSERT INTO commission_terms(org_id,party,rate_basis_points,effective_from,created_at)
                      VALUES(?,?,?,?,?)
                      ON CONFLICT(org_id,party,effective_from) DO UPDATE SET rate_basis_points=excluded.rate_basis_points""",
                   (org_id, party, rate, effective_from, int(time.time())))
        row = db.execute("""SELECT * FROM commission_terms WHERE org_id=? AND party=? AND effective_from=?
                            ORDER BY id DESC LIMIT 1""", (org_id, party, effective_from)).fetchone()
    return jsonify(term=dict(row)), 201


@app.get("/api/orgs/<int:org_id>/leads")
def list_leads(org_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        _, error = require_org(db, org_id, user)
        if error: return error
        rows = db.execute("SELECT * FROM leads WHERE org_id=? ORDER BY created_at DESC", (org_id,)).fetchall()
    return jsonify(leads=[dict(row) for row in rows])


@app.post("/api/orgs/<int:org_id>/leads")
def create_lead(org_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    body = json_body()
    name = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    if not 2 <= len(name) <= 100 or "@" not in email or len(email) > 254:
        return api_error("Enter a lead name and valid email.", 400)
    phone = str(body.get("phone", "")).strip()[:40]
    source = str(body.get("source", "Manual")).strip()[:60] or "Manual"
    notes = str(body.get("notes", "")).strip()[:1000]
    now = int(time.time())
    with connect() as db:
        _, error = require_org(db, org_id, user)
        if error: return error
        cursor = db.execute("""INSERT INTO leads(org_id,name,email,phone,source,status,notes,created_at,updated_at)
                               VALUES(?,?,?,?,?,'New',?,?,?)""", (org_id, name, email, phone, source, notes, now, now))
        row = db.execute("SELECT * FROM leads WHERE id=?", (cursor.lastrowid,)).fetchone()
    return jsonify(lead=dict(row)), 201


@app.patch("/api/orgs/<int:org_id>/leads/<int:lead_id>")
def update_lead(org_id, lead_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner", "broker")
    if error: return error
    body = json_body()
    status = str(body.get("status", ""))
    if status not in ("New", "Contacted", "Qualified", "Converted", "Lost"):
        return api_error("Choose a valid lead status.", 400)
    notes = str(body.get("notes", "")).strip()[:1000]
    with connect() as db:
        _, error = require_org(db, org_id, user)
        if error: return error
        cur = db.execute("UPDATE leads SET status=?,notes=?,updated_at=? WHERE id=? AND org_id=?",
                         (status, notes, int(time.time()), lead_id, org_id))
        if not cur.rowcount: return api_error("Lead not found.", 404)
        row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return jsonify(lead=dict(row))


@app.get("/api/orgs/<int:org_id>/dashboard")
def org_dashboard(org_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        _, error = require_org(db, org_id, user)
        if error: return error
        units = db.execute("""SELECT COUNT(*) total, SUM(CASE WHEN u.status='Rented' THEN 1 ELSE 0 END) occupied
                              FROM units u JOIN properties p ON p.id=u.property_id WHERE p.org_id=?""",
                           (org_id,)).fetchone()
        lead_rows = db.execute("SELECT status,COUNT(*) count FROM leads WHERE org_id=? GROUP BY status", (org_id,)).fetchall()
        summary = {
            "properties": db.execute("SELECT COUNT(*) FROM properties WHERE org_id=?", (org_id,)).fetchone()[0],
            "units": units["total"] or 0,
            "occupied_units": units["occupied"] or 0,
            "occupancy_percent": round(100 * (units["occupied"] or 0) / units["total"], 1) if units["total"] else 0,
            "active_rentals": db.execute("""SELECT COUNT(*) FROM applications a JOIN properties p ON p.id=a.property_id
                                            WHERE p.org_id=? AND a.status='Accepted'""", (org_id,)).fetchone()[0],
            "pending_applications": db.execute("""SELECT COUNT(*) FROM applications a JOIN properties p ON p.id=a.property_id
                                                  WHERE p.org_id=? AND a.status='Pending'""", (org_id,)).fetchone()[0],
            "open_issues": db.execute("""SELECT COUNT(*) FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id
                                         WHERE p.org_id=? AND t.status NOT IN ('Resolved','Skipped')""", (org_id,)).fetchone()[0],
            "pending_commission_paise": db.execute("""SELECT COALESCE(SUM(c.amount_paise),0) FROM commission_cycles c
                JOIN applications a ON a.id=c.application_id JOIN properties p ON p.id=a.property_id
                WHERE p.org_id=? AND c.status='Pending'""", (org_id,)).fetchone()[0],
            "leads_by_status": {row["status"]: row["count"] for row in lead_rows},
        }
    return jsonify(summary=summary)


@app.get("/api/orgs/<int:org_id>/export.csv")
def export_org_csv(org_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    kind = request.args.get("type", "commissions")
    if kind not in ("commissions", "properties", "issues", "leads"):
        return api_error("Choose a valid export type.", 400)
    with connect() as db:
        _, error = require_org(db, org_id, user)
        if error: return error
        if kind == "commissions":
            rows = [["Billing month", "Party", "Property", "Renter", "Owner", "Rate (bps)", "Amount (INR)", "Status"]]
            for row in db.execute("""SELECT c.billing_period,c.party,p.title,c.rate_basis_points,c.amount_paise,c.status,
                                     r.name renter_name,o.name owner_name FROM commission_cycles c
                                     JOIN applications a ON a.id=c.application_id JOIN properties p ON p.id=a.property_id
                                     JOIN users r ON r.id=a.renter_id JOIN users o ON o.id=p.owner_id
                                     WHERE p.org_id=? ORDER BY c.billing_period DESC,c.id""", (org_id,)).fetchall():
                rows.append([row["billing_period"], row["party"], row["title"], row["renter_name"], row["owner_name"],
                             row["rate_basis_points"], row["amount_paise"] / 100, row["status"]])
        elif kind == "properties":
            rows = [["ID", "Title", "Type", "Address", "Monthly rent", "Units", "Available", "Status", "Owner"]]
            for row in db.execute("""SELECT p.*,u.name owner_name,(SELECT COUNT(*) FROM units un WHERE un.property_id=p.id AND un.status='Available') available
                                     FROM properties p JOIN users u ON u.id=p.owner_id WHERE p.org_id=? ORDER BY p.id""", (org_id,)).fetchall():
                rows.append([row["id"], row["title"], row["property_type"], row["address"], row["monthly_rent"],
                             row["unit_count"], row["available"], row["status"], row["owner_name"]])
        elif kind == "issues":
            rows = [["ID", "Title", "Category", "Priority", "Status", "Property", "Renter", "Submitted"]]
            for row in db.execute("""SELECT t.*,p.title property_title,r.name renter_name FROM maintenance_tickets t
                                     JOIN properties p ON p.id=t.property_id JOIN users r ON r.id=t.renter_id
                                     WHERE p.org_id=? ORDER BY t.id""", (org_id,)).fetchall():
                rows.append([row["id"], row["title"], row["category"], row["priority"], row["status"],
                             row["property_title"], row["renter_name"],
                             datetime.fromtimestamp(row["created_at"], timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])
        else:
            rows = [["ID", "Name", "Email", "Phone", "Source", "Status", "Notes", "Created"]]
            for row in db.execute("SELECT * FROM leads WHERE org_id=? ORDER BY id", (org_id,)).fetchall():
                rows.append([row["id"], row["name"], row["email"], row["phone"], row["source"], row["status"], row["notes"],
                             datetime.fromtimestamp(row["created_at"], timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])
    return csv_response(rows, f"propmanager-{kind}-{org_id}.csv")


@app.get("/api/analytics")
def analytics_summary():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    role = user["role"]
    with connect() as db:
        if role == "renter":
            app_where, app_params = " WHERE a.renter_id=?", (user["id"],)
            prop_where, prop_params = (" WHERE p.id IN (SELECT property_id FROM applications WHERE renter_id=? AND status='Accepted')", (user["id"],))
            ticket_where, ticket_params = " WHERE t.renter_id=?", (user["id"],)
            comm_where, comm_params = " WHERE a.renter_id=? AND c.party='renter'", (user["id"],)
        elif role == "owner":
            app_where, app_params = " WHERE p.owner_id=?", (user["id"],)
            prop_where, prop_params = " WHERE p.owner_id=?", (user["id"],)
            ticket_where, ticket_params = " WHERE p.owner_id=?", (user["id"],)
            comm_where, comm_params = " WHERE p.owner_id=? AND c.party='owner'", (user["id"],)
        else:
            app_where, app_params = "", ()
            prop_where, prop_params = "", ()
            ticket_where, ticket_params = "", ()
            comm_where, comm_params = "", ()

        def groups(query, params):
            return [{"label": row["label"] or "Unknown", "value": row["value"]} for row in db.execute(query, params).fetchall()]

        units = db.execute("""SELECT COUNT(*) total, COALESCE(SUM(CASE WHEN u.status='Rented' THEN 1 ELSE 0 END),0) occupied
                              FROM units u JOIN properties p ON p.id=u.property_id""" + prop_where, prop_params).fetchone()
        charts = {
            "applications_by_status": groups("SELECT a.status label,COUNT(*) value FROM applications a JOIN properties p ON p.id=a.property_id" + app_where + " GROUP BY label ORDER BY value DESC", app_params),
            "applications_by_month": groups("SELECT strftime('%Y-%m',a.created_at,'unixepoch') label,COUNT(*) value FROM applications a JOIN properties p ON p.id=a.property_id" + app_where + " GROUP BY label ORDER BY label", app_params),
            "properties_by_type": groups("SELECT p.property_type label,COUNT(*) value FROM properties p" + prop_where + " GROUP BY label ORDER BY value DESC", prop_params),
            "tickets_by_status": groups("SELECT t.status label,COUNT(*) value FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id" + ticket_where + " GROUP BY label ORDER BY value DESC", ticket_params),
            "tickets_by_priority": groups("SELECT t.priority label,COUNT(*) value FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id" + ticket_where + " GROUP BY label ORDER BY value DESC", ticket_params),
            "tickets_by_category": groups("SELECT t.category label,COUNT(*) value FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id" + ticket_where + " GROUP BY label ORDER BY value DESC", ticket_params),
            "tickets_by_month": groups("SELECT strftime('%Y-%m',t.created_at,'unixepoch') label,COUNT(*) value FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id" + ticket_where + " GROUP BY label ORDER BY label", ticket_params),
            "commissions_by_month": groups("SELECT c.billing_period label,SUM(c.amount_paise) value FROM commission_cycles c JOIN applications a ON a.id=c.application_id JOIN properties p ON p.id=a.property_id" + comm_where + " GROUP BY label ORDER BY label", comm_params),
            "commissions_by_status": groups("SELECT c.status label,SUM(c.amount_paise) value FROM commission_cycles c JOIN applications a ON a.id=c.application_id JOIN properties p ON p.id=a.property_id" + comm_where + " GROUP BY label ORDER BY value DESC", comm_params),
        }
        if role == "broker":
            charts["leads_by_status"] = groups("SELECT status label,COUNT(*) value FROM leads GROUP BY label ORDER BY value DESC", ())
            charts["organizations"] = groups("SELECT o.name label,COUNT(p.id) value FROM organizations o LEFT JOIN properties p ON p.org_id=o.id GROUP BY o.id ORDER BY value DESC", ())

        monthly = {}
        for key, field in (("applications_by_month", "applications"), ("tickets_by_month", "issues"), ("commissions_by_month", "commission_paise")):
            for row in charts[key]:
                entry = monthly.setdefault(row["label"], {"month": row["label"], "applications": 0, "issues": 0, "commission_paise": 0})
                entry[field] = row["value"]

        property_rows = db.execute("""SELECT p.id,p.title,p.property_type,p.unit_count,p.status,
            (SELECT COUNT(*) FROM units u WHERE u.property_id=p.id AND u.status='Rented') occupied,
            (SELECT COUNT(*) FROM maintenance_tickets t WHERE t.property_id=p.id AND t.status NOT IN ('Resolved','Skipped')) open_issues
            FROM properties p""" + prop_where + " ORDER BY p.created_at DESC LIMIT 25", prop_params).fetchall()
        total_commissions = db.execute("""SELECT COALESCE(SUM(c.amount_paise),0) FROM commission_cycles c
            JOIN applications a ON a.id=c.application_id JOIN properties p ON p.id=a.property_id""" + comm_where, comm_params).fetchone()[0]
        occupancy = round(100 * (units["occupied"] or 0) / units["total"], 1) if units["total"] else 0

        if role == "renter":
            kpis = [
                {"label": "Applications", "value": db.execute("SELECT COUNT(*) FROM applications WHERE renter_id=?", (user["id"],)).fetchone()[0]},
                {"label": "Active rentals", "value": db.execute("SELECT COUNT(*) FROM applications WHERE renter_id=? AND status='Accepted'", (user["id"],)).fetchone()[0]},
                {"label": "Open issues", "value": db.execute("SELECT COUNT(*) FROM maintenance_tickets WHERE renter_id=? AND status NOT IN ('Resolved','Skipped')", (user["id"],)).fetchone()[0]},
                {"label": "Commission obligations", "value": total_commissions / 100},
            ]
        elif role == "owner":
            kpis = [
                {"label": "Listings", "value": db.execute("SELECT COUNT(*) FROM properties WHERE owner_id=?", (user["id"],)).fetchone()[0]},
                {"label": "Occupancy", "value": f"{occupancy}%"},
                {"label": "Pending applications", "value": db.execute("SELECT COUNT(*) FROM applications a JOIN properties p ON p.id=a.property_id WHERE p.owner_id=? AND a.status='Pending'", (user["id"],)).fetchone()[0]},
                {"label": "Commission obligations", "value": total_commissions / 100},
            ]
        else:
            kpis = [
                {"label": "Properties", "value": db.execute("SELECT COUNT(*) FROM properties").fetchone()[0]},
                {"label": "Occupancy", "value": f"{occupancy}%"},
                {"label": "Open issues", "value": db.execute("SELECT COUNT(*) FROM maintenance_tickets WHERE status NOT IN ('Resolved','Skipped')").fetchone()[0]},
                {"label": "Commission obligations", "value": total_commissions / 100},
            ]
    return jsonify(role=role, kpis=kpis, charts=charts, monthly=sorted(monthly.values(), key=lambda row: row["month"]),
                   properties=[dict(row) for row in property_rows])


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
                "unread_notifications": db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user["id"],)).fetchone()[0],
            }
        elif user["role"] == "owner":
            summary = {
                "listings": db.execute("SELECT COUNT(*) FROM properties WHERE owner_id=?", (user["id"],)).fetchone()[0],
                "pending_applications": db.execute("SELECT COUNT(*) FROM applications a JOIN properties p ON p.id=a.property_id WHERE p.owner_id=? AND a.status='Pending'", (user["id"],)).fetchone()[0],
                "open_tickets": db.execute("SELECT COUNT(*) FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id WHERE p.owner_id=? AND t.status NOT IN ('Resolved','Skipped')", (user["id"],)).fetchone()[0],
                "unread_notifications": db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user["id"],)).fetchone()[0],
            }
        else:
            ticket_counts = {
                row["status"]: row["count"]
                for row in db.execute("SELECT status, COUNT(*) AS count FROM maintenance_tickets GROUP BY status")
            }
            summary = {
                "properties": db.execute("SELECT COUNT(*) FROM properties").fetchone()[0],
                "active_rentals": db.execute("SELECT COUNT(*) FROM applications WHERE status='Accepted'").fetchone()[0],
                "pending_applications": db.execute("SELECT COUNT(*) FROM applications WHERE status='Pending'").fetchone()[0],
                "pending_tickets": ticket_counts.get("Pending", 0),
                "in_progress_tickets": ticket_counts.get("In Progress", 0),
                "resolved_tickets": ticket_counts.get("Resolved", 0),
                "skipped_tickets": ticket_counts.get("Skipped", 0),
                "pending_commission_amount_paise": db.execute("SELECT COALESCE(SUM(amount_paise),0) FROM commission_cycles WHERE status='Pending'").fetchone()[0],
                "unread_notifications": db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user["id"],)).fetchone()[0],
            }
    return jsonify(role=user["role"], summary=summary)


@app.get("/api/notifications")
def list_notifications():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    limit = min(max(request.args.get("limit", default=20, type=int) or 20, 1), 100)
    with connect() as db:
        rows = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ?",
                          (user["id"], limit)).fetchall()
        unread = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user["id"],)).fetchone()[0]
    return jsonify(notifications=[dict(row) for row in rows], unread=unread)


@app.patch("/api/notifications/<int:notification_id>/read")
def read_notification(notification_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        cur = db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notification_id, user["id"]))
        if not cur.rowcount: return api_error("Notification not found.", 404)
    return jsonify(status="read")


@app.post("/api/notifications/read-all")
def read_all_notifications():
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        db.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (user["id"],))
    return jsonify(status="read")


@app.get("/api/applications")
def list_applications():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    query = """SELECT a.*, p.title property_title, p.property_type, p.address, p.monthly_rent, r.name renter_name, r.email renter_email, o.name owner_name, un.unit_label
               FROM applications a JOIN properties p ON p.id=a.property_id JOIN users r ON r.id=a.renter_id JOIN users o ON o.id=p.owner_id
               LEFT JOIN units un ON un.id=a.unit_id"""
    params = ()
    if user["role"] == "renter": query += " WHERE a.renter_id=?"; params = (user["id"],)
    elif user["role"] == "owner": query += " WHERE p.owner_id=?"; params = (user["id"],)
    query += " ORDER BY a.created_at DESC"
    with connect() as db: rows = db.execute(query, params).fetchall()
    return jsonify(applications=[dict(row) for row in rows])


@app.get("/api/applications/<int:application_id>")
def get_application(application_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    query = """SELECT a.*, p.title property_title, p.address, p.monthly_rent, p.owner_id,
               r.name renter_name, r.email renter_email, o.name owner_name, un.unit_label
               FROM applications a JOIN properties p ON p.id=a.property_id JOIN users r ON r.id=a.renter_id
               JOIN users o ON o.id=p.owner_id LEFT JOIN units un ON un.id=a.unit_id WHERE a.id=?"""
    with connect() as db:
        row = db.execute(query, (application_id,)).fetchone()
        if not row: return api_error("Application not found.", 404)
        if user["role"] == "renter" and row["renter_id"] != user["id"]: return api_error("Application not found.", 404)
        if user["role"] == "owner" and row["owner_id"] != user["id"]: return api_error("Application not found.", 404)
        events = db.execute("""SELECT e.id,e.event_type,e.old_status,e.new_status,e.note,e.created_at,u.name actor_name
                               FROM application_events e JOIN users u ON u.id=e.actor_id
                               WHERE e.application_id=? ORDER BY e.created_at,e.id""", (application_id,)).fetchall()
    return jsonify(application=dict(row), history=[dict(event) for event in events])


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
    unit_id = body.get("unit_id")
    try: unit_id = int(unit_id) if unit_id not in (None, "") else None
    except (TypeError, ValueError): return api_error("Choose a valid unit.", 400)
    try:
        with connect() as db:
            prop = db.execute("SELECT id,owner_id,title,status FROM properties WHERE id=?", (property_id,)).fetchone()
            if not prop or prop["status"] != "Available": return api_error("That listing is no longer available.", 404)
            if unit_id is not None:
                unit = db.execute("SELECT id FROM units WHERE id=? AND property_id=? AND status='Available'", (unit_id, property_id)).fetchone()
                if not unit: return api_error("Choose an available unit.", 409)
            now = int(time.time())
            cur = db.execute("INSERT INTO applications(property_id,renter_id,message,unit_id,created_at) VALUES(?,?,?,?,?)",
                             (property_id, user["id"], message, unit_id, now))
            app_id = cur.lastrowid
            record_application_event(db, app_id, user["id"], "submitted", None, "Pending", message, now)
            notify(db, prop["owner_id"], "application", "New rental application",
                   f"{user['name']} applied for {prop['title']}.", f"/applications/{app_id}", now)
    except sqlite3.IntegrityError:
        return api_error("You have already applied for this property.", 409)
    return jsonify(id=app_id, status="Pending"), 201


@app.post("/api/applications/<int:application_id>/decision")
def decide_application(application_id):
    csrf_error = require_csrf()
    if csrf_error: return csrf_error
    user, error = need_role("owner")
    if error: return error
    body = json_body()
    status = str(body.get("status", ""))
    reason = str(body.get("reason", "")).strip()[:500]
    if status not in ("Accepted", "Declined"): return api_error("Choose accept or decline.", 400)
    with connect() as db:
        now = int(time.time())
        application = db.execute("""SELECT a.*, p.owner_id, p.title property_title FROM applications a
                                    JOIN properties p ON p.id=a.property_id
                                    WHERE a.id=? AND a.status='Pending' AND p.owner_id=?""",
                                 (application_id, user["id"])).fetchone()
        if not application: return api_error("Application not found or already decided.", 404)
        unit_id = application["unit_id"]
        if status == "Accepted":
            requested = body.get("unit_id")
            if requested not in (None, ""):
                try: requested = int(requested)
                except (TypeError, ValueError): return api_error("Choose a valid unit.", 400)
                unit = db.execute("SELECT id FROM units WHERE id=? AND property_id=? AND status='Available'",
                                  (requested, application["property_id"])).fetchone()
                if not unit: return api_error("Choose an available unit.", 409)
                unit_id = requested
            elif not unit_id:
                unit = db.execute("SELECT id FROM units WHERE property_id=? AND status='Available' ORDER BY id LIMIT 1",
                                  (application["property_id"],)).fetchone()
                if not unit: return api_error("No unit is available for this listing.", 409)
                unit_id = unit["id"]
            else:
                unit = db.execute("SELECT id FROM units WHERE id=? AND property_id=? AND status='Available'",
                                  (unit_id, application["property_id"])).fetchone()
                if not unit: return api_error("The selected unit is no longer available.", 409)
            db.execute("UPDATE units SET status='Rented' WHERE id=?", (unit_id,))
        db.execute("UPDATE applications SET status=?,accepted_at=?,unit_id=?,decline_reason=? WHERE id=?",
                   (status, now if status == "Accepted" else None, unit_id,
                    reason if status == "Declined" else "", application_id))
        if status == "Accepted":
            db.execute("UPDATE properties SET status='Rented' WHERE id=?", (application["property_id"],))
        record_application_event(db, application_id, user["id"], "decision", "Pending", status,
                                 reason if status == "Declined" else "", now)
        title = "Application accepted" if status == "Accepted" else "Application declined"
        detail = f" Your reason: {reason}" if status == "Declined" and reason else ""
        notify(db, application["renter_id"], "decision", title,
               f"Your application for {application['property_title']} was {status.lower()}.{detail}",
               f"/applications/{application_id}", now)
        for broker in db.execute("SELECT id FROM users WHERE role='broker'").fetchall():
            notify(db, broker["id"], "application", f"Application {status.lower()}",
                   f"{application['property_title']} · {application['renter_id']}", f"/applications/{application_id}", now)
    if status == "Accepted":
        generate_commission_cycles(datetime.now(timezone.utc).strftime("%Y-%m"), application_id)
    return jsonify(status=status, unit_id=unit_id, decline_reason=reason if status == "Declined" else "")


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
    query = """SELECT a.id,p.monthly_rent,p.org_id FROM applications a JOIN properties p ON p.id=a.property_id
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
            for party in ("renter", "owner"):
                rate = 1000
                if application["org_id"]:
                    term = db.execute("""SELECT rate_basis_points FROM commission_terms
                        WHERE org_id=? AND party=? AND effective_from<=?
                        ORDER BY effective_from DESC,id DESC LIMIT 1""",
                        (application["org_id"], party, start_ts)).fetchone()
                    if term:
                        rate = term["rate_basis_points"]
                # Store INR paise; basis points are hundredths of a percent of monthly rent.
                amount_paise = (application["monthly_rent"] * 100 * rate) // 10000
                cursor = db.execute("""INSERT OR IGNORE INTO commission_cycles
                    (application_id,billing_period,party,rate_basis_points,amount_paise,status,created_at)
                    VALUES(?,?,?,?,?,'Pending',?)""", (application["id"],billing_period,party,rate,amount_paise,now))
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
        rental = db.execute("""SELECT a.property_id,a.renter_id,a.unit_id,p.owner_id,p.title property_title
                              FROM applications a JOIN properties p ON p.id=a.property_id
                              WHERE a.id=? AND a.status='Accepted' AND (?='broker' OR p.owner_id=?)""",
                            (application_id,user["role"],user["id"])).fetchone()
        if not rental: return api_error("Active rental not found.", 404)
        now = int(time.time())
        db.execute("UPDATE applications SET status='Ended',ended_at=? WHERE id=?", (now,application_id))
        if rental["unit_id"]:
            db.execute("UPDATE units SET status='Available' WHERE id=?", (rental["unit_id"],))
        db.execute("UPDATE properties SET status='Available' WHERE id=?", (rental["property_id"],))
        record_application_event(db, application_id, user["id"], "rental_ended", "Accepted", "Ended", reason, now)
        message = f"The rental for {rental['property_title']} has ended. {reason}".strip()
        notify(db, rental["renter_id"], "rental", "Rental ended", message, f"/applications/{application_id}", now)
        notify(db, rental["owner_id"], "rental", "Rental ended", message, f"/applications/{application_id}", now)
    return jsonify(status="Ended", ended_at=now, reason=reason)


@app.get("/api/commissions")
def list_commissions():
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    generate_commission_cycles(period)
    query = """SELECT c.*, a.status application_status, p.title property_title, p.monthly_rent,
                            r.name renter_name, o.name owner_name
                            FROM commission_cycles c JOIN applications a ON a.id=c.application_id JOIN properties p ON p.id=a.property_id
                            JOIN users r ON r.id=a.renter_id JOIN users o ON o.id=p.owner_id
                            """
    params = ()
    if user["role"] == "renter":
        query += " WHERE a.renter_id=? AND c.party='renter'"
        params = (user["id"],)
    elif user["role"] == "owner":
        query += " WHERE p.owner_id=? AND c.party='owner'"
        params = (user["id"],)
    query += " ORDER BY c.billing_period DESC,c.created_at DESC,c.party"
    with connect() as db:
        rows = db.execute(query, params).fetchall()
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
                AND similar.status NOT IN ('Resolved','Skipped')) AS similar_issue_count,
               (SELECT COUNT(DISTINCT similar.renter_id) FROM maintenance_tickets similar WHERE similar.id != t.id
                AND similar.property_id=t.property_id AND similar.category=t.category
                AND similar.status NOT IN ('Resolved','Skipped')) AS similar_resident_count
               FROM maintenance_tickets t JOIN properties p ON p.id=t.property_id JOIN users r ON r.id=t.renter_id JOIN users o ON o.id=p.owner_id"""
    params = ()
    if user["role"] == "renter": query += " WHERE t.renter_id=?"; params = (user["id"],)
    elif user["role"] == "owner": query += " WHERE p.owner_id=?"; params = (user["id"],)
    if request.args.get("sort") == "priority":
        query += (" ORDER BY CASE t.priority WHEN 'Urgent' THEN 4 WHEN 'High' THEN 3 "
                  "WHEN 'Medium' THEN 2 ELSE 1 END DESC, t.created_at ASC")
    else:
        query += " ORDER BY t.created_at DESC"
    now = int(time.time())
    with connect() as db: rows = db.execute(query, params).fetchall()
    tickets = []
    for row in rows:
        item = dict(row)
        item["age_hours"] = max(0, (now - item["created_at"]) // 3600)
        tickets.append(item)
    return jsonify(tickets=tickets)


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
        prop = db.execute("SELECT owner_id,title FROM properties WHERE id=?", (property_id,)).fetchone()
        now = int(time.time())
        cur = db.execute("INSERT INTO maintenance_tickets(property_id,renter_id,title,description,category,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (property_id,user["id"],title,description,category,priority,now,now))
        ticket_id = cur.lastrowid
        db.execute("INSERT INTO ticket_events(ticket_id,actor_id,event_type,new_status,note,created_at) VALUES(?,?,'created','Pending',?,?)", (ticket_id,user["id"],title,now))
        message = f"{priority} priority {category.lower()} issue: {title}"
        notify(db, prop["owner_id"], "ticket", "New issue reported", message, f"/tickets/{ticket_id}", now)
        for broker in db.execute("SELECT id FROM users WHERE role='broker'").fetchall():
            notify(db, broker["id"], "ticket", "New issue in queue", message, f"/tickets/{ticket_id}", now)
    return jsonify(id=ticket_id, status="Pending"), 201


@app.get("/api/tickets/<int:ticket_id>")
def get_ticket(ticket_id):
    user, error = need_role("renter", "owner", "broker")
    if error: return error
    with connect() as db:
        row = db.execute("""SELECT t.*,p.title property_title,p.address,r.name renter_name,p.owner_id,
                           (SELECT COUNT(*) FROM maintenance_tickets s WHERE s.id!=t.id AND s.property_id=t.property_id
                            AND s.category=t.category AND s.status NOT IN ('Resolved','Skipped')) AS similar_issue_count,
                            (SELECT COUNT(DISTINCT s.renter_id) FROM maintenance_tickets s WHERE s.id!=t.id AND s.property_id=t.property_id
                             AND s.category=t.category AND s.status NOT IN ('Resolved','Skipped')) AS similar_resident_count
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
    if status == "Skipped" and not note:
        return api_error("Add a reason before skipping an issue.", 400)
    with connect() as db:
        existing = db.execute("SELECT status,manager_note,renter_id,title FROM maintenance_tickets WHERE id=?", (ticket_id,)).fetchone()
        if not existing: return api_error("Ticket not found.", 404)
        now = int(time.time())
        cur = db.execute("UPDATE maintenance_tickets SET status=?,manager_note=?,updated_at=? WHERE id=?", (status,note,now,ticket_id))
        if existing["status"] != status or existing["manager_note"] != note:
            event_type = "status_changed" if existing["status"] != status else "note_updated"
            db.execute("INSERT INTO ticket_events(ticket_id,actor_id,event_type,old_status,new_status,note,created_at) VALUES(?,?,?,?,?,?,?)", (ticket_id,user["id"],event_type,existing["status"],status,note,now))
            if existing["status"] != status:
                notify(db, existing["renter_id"], "ticket", f"Issue {status.lower()}",
                       f"{existing['title']} is now {status}.", f"/tickets/{ticket_id}", now)
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


DEMO_PASSWORD = "DemoPass123!"
DEMO_EMAILS = {
    "broker": "broker@propmanager.demo",
    "owner": "owner@propmanager.demo",
    "renter_a": "renter-a@propmanager.demo",
    "renter_b": "renter-b@propmanager.demo",
    "renter_c": "renter-c@propmanager.demo",
}
STOCK_IMAGES = (
    "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1493809842364-78817add7ffb?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1497366811353-6870744d04b2?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=900&q=80",
)


@app.cli.command("seed-demo")
@click.option("--reset", is_flag=True, help="Remove existing demo records before seeding.")
@click.option("--force", is_flag=True, help="Allow seeding when COOKIE_SECURE=true (hosted database).")
def seed_demo(reset, force):
    """Create demo users, stock-image listings, rentals, issues and notifications."""
    init_db()
    if COOKIE_SECURE and not force:
        raise click.ClickException("Refusing to seed a hosted database. Set COOKIE_SECURE=false locally or pass --force.")
    now = int(time.time())
    day, hour = 86400, 3600

    def add_user(email, name, role):
        cursor = db.execute("INSERT INTO users(email,name,role,password_hash,created_at) VALUES(?,?,?,?,?)",
                            (email, name, role, hasher.hash(DEMO_PASSWORD), now - 60 * day))
        return cursor.lastrowid

    def add_property(title, property_type, address, rent, units, image_index, status="Available"):
        cursor = db.execute("""INSERT INTO properties(owner_id,title,property_type,address,description,monthly_rent,
                               bedrooms,unit_count,status,image_url,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                            (owner_id, title, property_type, address, "Demo listing with verified units and broker coordination.",
                             rent, 2 if property_type == "Apartment" else 1, units, status, STOCK_IMAGES[image_index], now - 45 * day))
        property_id = cursor.lastrowid
        prefix = {"Apartment": "Flat", "PG/Hostel": "Room", "Office/Commercial": "Suite"}[property_type]
        for number in range(1, units + 1):
            db.execute("INSERT INTO units(property_id,unit_label,monthly_rent,status,created_at) VALUES(?,?,?,'Available',?)",
                       (property_id, f"{prefix} {100 + number}", rent, now - 45 * day))
        return property_id

    def add_application(property_id, renter_id, status, created_days, accepted_days=None,
                        unit_number=None, message="", actor_id=None):
        created = now - int(created_days * day)
        accepted = now - int(accepted_days * day) if accepted_days is not None else None
        unit_id = None
        if unit_number:
            unit = db.execute("SELECT id FROM units WHERE property_id=? ORDER BY id LIMIT 1 OFFSET ?",
                              (property_id, unit_number - 1)).fetchone()
            unit_id = unit["id"] if unit else None
        if status == "Accepted" and unit_id:
            db.execute("UPDATE units SET status='Rented' WHERE id=?", (unit_id,))
        if status == "Accepted":
            db.execute("UPDATE properties SET status='Rented' WHERE id=?", (property_id,))
        cursor = db.execute("""INSERT INTO applications(property_id,renter_id,message,status,unit_id,accepted_at,ended_at,created_at)
                               VALUES(?,?,?,?,?,?,NULL,?)""",
                            (property_id, renter_id, message, status, unit_id,
                             accepted if status == "Accepted" else None, created))
        application_id = cursor.lastrowid
        record_application_event(db, application_id, renter_id, "submitted", None, "Pending", message, created)
        if status in ("Accepted", "Declined"):
            record_application_event(db, application_id, actor_id or owner_id, "decision", "Pending", status, "", accepted or created)
        return application_id

    def add_ticket(property_id, renter_id, title, description, category, priority, status, hours_ago, note=""):
        created = now - int(hours_ago * hour)
        cursor = db.execute("""INSERT INTO maintenance_tickets(property_id,renter_id,title,description,category,priority,
                               status,manager_note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                            (property_id, renter_id, title, description, category, priority, status, note, created, created))
        ticket_id = cursor.lastrowid
        db.execute("""INSERT INTO ticket_events(ticket_id,actor_id,event_type,new_status,note,created_at)
                      VALUES(?,?,'created','Pending',?,?)""", (ticket_id, renter_id, title, created))
        if status != "Pending":
            db.execute("""INSERT INTO ticket_events(ticket_id,actor_id,event_type,old_status,new_status,note,created_at)
                          VALUES(?,?,'status_changed','Pending',?,?,?)""", (ticket_id, broker_id, status, note, created + 300))
        return ticket_id

    with connect() as db:
        if reset:
            db.execute("DELETE FROM organizations WHERE created_by IN (SELECT id FROM users WHERE email LIKE '%@propmanager.demo')")
            for email in DEMO_EMAILS.values():
                user = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
                if not user:
                    continue
                user_id = user["id"]
                db.execute("DELETE FROM ticket_events WHERE actor_id=?", (user_id,))
                db.execute("DELETE FROM application_events WHERE actor_id=?", (user_id,))
                db.execute("DELETE FROM users WHERE id=?", (user_id,))
            db.execute("DELETE FROM demo_state WHERE key='demo_seeded'")
        if db.execute("SELECT 1 FROM demo_state WHERE key='demo_seeded'").fetchone():
            raise click.ClickException("Demo data is already seeded. Use --reset to recreate it.")

        broker_id = add_user(DEMO_EMAILS["broker"], "Asha Mehta", "broker")
        owner_id = add_user(DEMO_EMAILS["owner"], "Rohan Kapoor", "owner")
        renter_a = add_user(DEMO_EMAILS["renter_a"], "Meera Iyer", "renter")
        renter_b = add_user(DEMO_EMAILS["renter_b"], "Arjun Nair", "renter")
        renter_c = add_user(DEMO_EMAILS["renter_c"], "Tara Deshmukh", "renter")

        apartment = add_property("Lavender Apartments", "Apartment", "Baner, Pune", 32000, 4, 0, "Rented")
        pg = add_property("Willow PG Rooms", "PG/Hostel", "Kothrud, Pune", 14500, 6, 1, "Rented")
        office = add_property("Cedar Business Park", "Office/Commercial", "Hinjawadi, Pune", 185000, 3, 2, "Rented")
        available = [
            add_property("Sunrise Residency", "Apartment", "Koregaon Park, Pune", 28000, 3, 3),
            add_property("Garden View Lofts", "Apartment", "FC Road, Pune", 36000, 4, 4),
            add_property("Maple Staff Housing", "PG/Hostel", "Viman Nagar, Pune", 12000, 10, 5),
            add_property("Orion Corporate Suites", "Office/Commercial", "Bandra, Mumbai", 240000, 5, 6),
            add_property("Harbour Studio Homes", "Apartment", "Marine Drive, Mumbai", 52000, 2, 7),
        ]

        add_application(apartment, renter_a, "Accepted", 40, 38, 1, "Quiet professional, moving in next month.")
        add_application(pg, renter_b, "Accepted", 20, 18, 1, "Looking for a room near the metro.")
        add_application(pg, renter_c, "Accepted", 15, 14, 2, "Sharing with a colleague.")
        add_application(office, renter_c, "Accepted", 10, 9, 1, "Small design team, two-year lease.")
        add_application(available[0], renter_a, "Pending", 2, message="Interested in a second home.")
        add_application(available[1], renter_b, "Declined", 3, accepted_days=2, message="Budget did not work out.")
        add_application(available[2], renter_c, "Pending", 1, message="Staff accommodation enquiry.")

        add_ticket(apartment, renter_a, "Lift making a noise", "The lift rattles between floors 2 and 3.",
                   "Maintenance", "High", "In Progress", 36, "Technician visits tomorrow morning.")
        add_ticket(apartment, renter_a, "Street light is out", "The street light outside the gate has been out for two nights.",
                   "Neighbourhood safety", "Medium", "Resolved", 240, "Municipal repair completed.")
        add_ticket(apartment, renter_a, "Kitchen tap leaking", "The kitchen tap drips continuously.",
                   "Plumbing", "High", "Pending", 6)
        add_ticket(pg, renter_b, "Main door lock jammed", "The main door lock jammed late at night.",
                   "Personal safety", "Urgent", "Pending", 3)
        add_ticket(pg, renter_b, "Bathroom tap dripping", "A tap in the common bathroom will not stop dripping.",
                   "Plumbing", "Medium", "Pending", 20)
        add_ticket(pg, renter_c, "Water heater stopped working", "The room geyser does not heat water.",
                   "Appliance", "High", "In Progress", 48, "Electrician arranged with the owner.")
        add_ticket(pg, renter_c, "Another leaking tap", "The tap in room 102 leaks all day.",
                   "Plumbing", "Medium", "Pending", 22)
        add_ticket(office, renter_c, "AC not cooling", "The conference room AC is not cooling.",
                   "Appliance", "High", "Skipped", 96, "Owner is handling service outside PropManager.")
        add_ticket(office, renter_c, "Security badge failed", "My access badge stopped working at the gate.",
                   "Security/access", "Urgent", "Resolved", 120, "Badge reissued by reception.")

        notify(db, broker_id, "ticket", "Urgent issue in queue", "Personal safety issue at Willow PG Rooms.", "/tickets/4", now - 3 * hour)
        notify(db, owner_id, "application", "New rental application", "Meera Iyer applied for Sunrise Residency.", "/applications/5", now - 2 * day)
        notify(db, renter_a, "decision", "Application accepted", "Your application for Lavender Apartments was accepted.", "/applications/1", now - 38 * day)
        notify(db, renter_b, "ticket", "Issue in progress", "Lift noise is being handled by the broker.", "/tickets/1", now - 30 * hour)
        notify(db, renter_c, "ticket", "Issue skipped", "AC not cooling was skipped with a reason.", "/tickets/8", now - 90 * hour)

        org_cursor = db.execute("INSERT INTO organizations(name,slug,created_by,created_at) VALUES(?,?,?,?)",
                                ("Northstar Property Partners", "northstar-property-partners", owner_id, now - 60 * day))
        org_id = org_cursor.lastrowid
        db.execute("INSERT INTO org_members(org_id,user_id,role,created_at) VALUES(?,?,'org_admin',?)", (org_id, owner_id, now - 60 * day))
        db.execute("INSERT INTO org_members(org_id,user_id,role,created_at) VALUES(?,?,'broker',?)", (org_id, broker_id, now - 60 * day))
        for property_id in (apartment, pg, office, available[3]):
            db.execute("UPDATE properties SET org_id=? WHERE id=?", (org_id, property_id))
        effective = int((datetime.now(timezone.utc).replace(day=1) - timedelta(days=45)).timestamp())
        db.execute("INSERT INTO commission_terms(org_id,party,rate_basis_points,effective_from,created_at) VALUES(?,?,?,?,?)",
                   (org_id, "owner", 900, effective, now - 45 * day))
        db.execute("INSERT INTO commission_terms(org_id,party,rate_basis_points,effective_from,created_at) VALUES(?,?,?,?,?)",
                   (org_id, "renter", 1000, effective, now - 45 * day))
        db.execute("""INSERT INTO org_invitations(org_id,email,role,token_hash,expires_at,accepted_by,created_at)
                      VALUES(?,?,'manager',?,?,NULL,?)""",
                   (org_id, "ops@northstar.demo", hashlib.sha256(secrets.token_urlsafe(32).encode()).hexdigest(), now + 7 * 86400, now))
        for name, email, phone, source, status, notes, days in (
            ("Sunita Rao", "sunita@example.test", "98765 11111", "Referral", "Qualified", "Looking for a PG near Kothrud.", 9),
            ("Vikram Sethi", "vikram@example.test", "", "Website", "New", "Interested in office floor.", 6),
            ("Neha Patil", "neha@example.test", "98765 22222", "Referral", "Contacted", "Follow up on apartment budget.", 4),
            ("Deepak Shah", "deepak@example.test", "", "Walk-in", "Converted", "Signed for Harbour Studio Homes.", 12),
            ("Rina Kulkarni", "rina@example.test", "", "Website", "Lost", "Budget did not match.", 20),
        ):
            db.execute("""INSERT INTO leads(org_id,name,email,phone,source,status,notes,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?)""",
                       (org_id, name, email, phone, source, status, notes, now - days * day, now - days * day))
        db.execute("INSERT INTO demo_state(key,value) VALUES('demo_seeded',?)",
                   (datetime.now(timezone.utc).isoformat(),))

    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    previous_month = (datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    generate_commission_cycles(previous_month)
    generate_commission_cycles(current_month)
    with connect() as db:
        rows = db.execute("SELECT id FROM commission_cycles ORDER BY id LIMIT 3").fetchall()
        if rows: db.execute("UPDATE commission_cycles SET status='Paid' WHERE id=?", (rows[0]["id"],))
        if len(rows) > 1: db.execute("UPDATE commission_cycles SET status='Waived' WHERE id=?", (rows[1]["id"],))
    click.echo("Demo data seeded. Sign in with any @propmanager.demo account using " + DEMO_PASSWORD + ".")
    click.echo("Broker: " + DEMO_EMAILS["broker"] + " | Owner: " + DEMO_EMAILS["owner"] + " | Renters: renter-a/b/c@propmanager.demo")


@app.cli.command("backup")
@click.option("--output", default=None, help="Destination path; defaults to a timestamped file beside the database.")
def backup_database(output):
    """Create a consistent backup of the SQLite database without stopping the app."""
    if not DATABASE.exists():
        raise click.ClickException(f"Database not found at {DATABASE}.")
    destination = Path(output) if output else DATABASE.with_name(
        f"{DATABASE.stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.backup.sqlite3"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(DATABASE)
    target = sqlite3.connect(destination)
    try:
        with target:
            source.backup(target)
    finally:
        source.close()
        target.close()
    click.echo(f"Backup written to {destination}")


@app.cli.command("restore")
@click.argument("backup_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def restore_database(backup_file, yes):
    """Restore the SQLite database from a backup that passes an integrity check."""
    source = sqlite3.connect(backup_file)
    try:
        result = source.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise click.ClickException(f"Not a valid SQLite backup: {exc}") from exc
    finally:
        source.close()
    if result != "ok":
        raise click.ClickException("Backup failed its integrity check; nothing was changed.")
    if not yes:
        click.confirm(f"Replace {DATABASE} with {backup_file}?", abort=True)
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DATABASE.with_name(DATABASE.name + ".restore-tmp")
    try:
        shutil.copy2(backup_file, temporary)
        os.replace(temporary, DATABASE)
    finally:
        if temporary.exists():
            temporary.unlink()
    click.echo(f"Database restored from {backup_file}")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
