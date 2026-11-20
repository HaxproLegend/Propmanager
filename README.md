# PropManager

PropManager is a broker-supported rental service prototype. It has a public landing page, server-backed renter/owner/broker accounts, rental listings and applications, broker-coordinated maintenance tickets, and a manual placement commission ledger.

## Run locally

Requirements: Node.js 20.19+ (or 22.12+) and Python 3.10+.

1. In the project folder, run `npm install` and then `npm run dev`.
2. In another terminal, create a Python environment and install `backend/requirements-dev.txt` (includes Flask and pytest).
3. Copy `.env.example` to `.env`. For local development, `COOKIE_SECURE=false` works with localhost; set it to `true` behind HTTPS in deployment.
4. Start the API from the project folder with `python -m flask --app backend.app run`.
5. Open the Vite address shown in the first terminal (usually `http://localhost:5173`). Vite forwards `/api` requests to Flask.

The SQLite database is created at `backend/instance/propmanager.sqlite3` when Flask starts. It contains account records, Argon2id password hashes, hashed session tokens, listings, applications, ticket records and commission records. Keep this local database out of Git.

Each owner can manage multiple listings, and a renter may hold application and maintenance records for multiple accepted rentals. The signed-in Profile view shows the account role and email and lets the user update their display name; role and email stay read-only.

Run the Flask API checks with `.venv/bin/python -m pytest` from the project folder. Tests use a temporary SQLite database and cover all API routes, role restrictions and the end-to-end rental/ticket workflow.

To create a broker account, run `python -m flask --app backend.app create-broker` and follow the prompts. Broker privilege is never offered by public registration. Renter and owner accounts can be created on the landing page.

## Demo flow

1. Create an owner account and publish a home listing.
2. Create a renter account in a separate browser profile, browse the listing and apply.
3. Sign in as the owner and accept the application.
4. Sign in as a broker created with the CLI. Record a manual placement fee for the accepted application.
5. Sign back in as the renter, submit a maintenance request for the accepted home, then use the broker view to filter, search, add a note and move the ticket through its lifecycle.

The commission is a manually entered ledger amount. Its business formula and any real payment collection are intentionally undecided.

## Authentication in this version

- Passwords are hashed with Argon2id; this is one-way hashing, not reversible encryption. Use HTTPS/TLS when hosted to protect credentials in transit; SQLite disk encryption is not configured.
- The server issues random opaque session tokens, stores only their SHA-256 hashes, checks them on each signed-in request and removes a token on sign-out.
- Session cookies are `HttpOnly` and `SameSite=Lax`; `COOKIE_SECURE=true` must be used behind HTTPS in deployment.
- State-changing auth requests use a CSRF token. Sign-in failures are throttled after repeated attempts.
- Roles come from the server account record. The browser cannot grant itself broker access.

Use HTTPS in any shared or production deployment. `COOKIE_SECURE=false` is only for local HTTP development. This is an OJT prototype, not a production identity platform. Email verification, password reset, MFA, and administrator account management remain future work; do not claim these are implemented.

## Project structure

- `src/` — React landing, sign-in, registration and renter/owner/broker workspaces.
- `backend/app.py` — Flask JSON API, SQLite persistence, password verification, sessions and role-scoped workflows.
- `backend/requirements.txt` — Python dependencies.
- `backend/tests/` — pytest suite for Flask routes and role-scoped workflows.
- `docs/API.md` — backend route, role and payload contract.
- `css/`, `js/` — original vanilla JavaScript/IndexedDB maintenance demo modules, retained as migration reference while the authenticated workflow is built.
- `docs/PRD.md` — current implemented scope and relationship to the submitted PRD.
- `docs/GOOD_TO_HAVE_BACKLOG.md` — partner-suggested additions, mapped to current scope and later releases.

This backend is the working local MVP for the agreed flows, not a production identity or payments platform. Email verification, password reset, MFA, external payment collection, database backup and hosted deployment still need separate work.
