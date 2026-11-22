# PropManager

PropManager is a broker-supported rental service prototype. It has a public landing page, server-backed renter/owner/broker accounts, rental listings and applications, broker-coordinated issue tickets, and a manual placement commission ledger.

## Project layout

```text
Propmanager/
├── backend/                 Flask API, SQLite setup, and pytest suite
├── frontend/                React/Vite application
│   ├── src/                  Active landing, authentication, and workspace UI
│   ├── legacy/               Original vanilla JS/CSS prototype kept for reference
│   ├── index.html            Vite entry page
│   ├── package.json          Frontend dependencies and scripts
│   └── vite.config.js        Local `/api` proxy
├── docs/                     API reference, PRD, wireframes, and feature notes
├── .github/                  Backend CI workflow
├── .env.example              Local Flask environment template
├── vercel.json               Frontend build settings and hosted API rewrite
└── README.md
```

## Run locally

Requirements: Node.js 20.19+ (or 22.12+) and Python 3.10+.

1. In one terminal, install and start the frontend:

   ```sh
   cd frontend
   npm ci
   npm run dev
   ```

2. In another terminal, from the repository root, create a Python environment and install the backend requirements:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r backend/requirements-dev.txt
   ```

3. Copy `.env.example` to `.env`. For local HTTP development, keep `COOKIE_SECURE=false`.
4. From the repository root, start Flask:

   ```sh
   python -m flask --app backend.app run
   ```

5. Open the Vite address shown in the frontend terminal (usually `http://localhost:5173`). Vite forwards `/api` requests to the local Flask API at `http://127.0.0.1:5000` by default. To use another API during frontend development, set `VITE_API_PROXY_TARGET` in `frontend/.env.local`.

The SQLite database is created at `backend/instance/propmanager.sqlite3` when Flask starts. It contains account records, Argon2id password hashes, hashed session tokens, listings, applications, ticket records, and commission records. The local database is ignored by Git.

Run the Flask API checks from the repository root with:

```sh
.venv/bin/python -m pytest
```

Tests use a temporary SQLite database and cover API routes, role restrictions, and the end-to-end rental/ticket workflow.

To create a broker account, run this from the repository root and follow the prompts:

```sh
python -m flask --app backend.app create-broker
```

Broker privilege is never offered by public registration. Renter and owner accounts can be created on the landing page.

## Demo flow

1. Create an owner account and publish a home listing.
2. Create a renter account in a separate browser profile, browse the listing, and apply.
3. Sign in as the owner and accept the application.
4. Sign in as a broker created with the CLI. Record a manual placement fee for the accepted application.
5. Sign back in as the renter, submit an issue request for the accepted home, then use the broker view to filter, search, add a note, and move the ticket through its lifecycle.

The commission is a manually entered ledger amount. Its business formula and any real payment collection are intentionally undecided.

## Authentication in this version

- Passwords are hashed with Argon2id; this is one-way hashing, not reversible encryption. Use HTTPS/TLS when hosted to protect credentials in transit; SQLite disk encryption is not configured.
- The server issues random opaque session tokens, stores only their SHA-256 hashes, checks them on each signed-in request, and removes a token on sign-out.
- Session cookies are `HttpOnly` and `SameSite=Lax`; `COOKIE_SECURE=true` must be used behind HTTPS in deployment.
- State-changing auth requests use a CSRF token. Sign-in failures are throttled after repeated attempts.
- Roles come from the server account record. The browser cannot grant itself broker access.

Use HTTPS in any shared or production deployment. `COOKIE_SECURE=false` is only for local HTTP development. This is an OJT prototype, not a production identity platform. Email verification, password reset, MFA, and administrator account management remain future work; do not claim these are implemented.

## Deployment

Vercel is configured in the repository-root `vercel.json` to install and build the app from `frontend/`, publish `frontend/dist`, and forward `/api/*` requests to the Flask API. Keep the Vercel project root set to the repository root.

## Scope notes

Each owner can manage multiple listings, and a renter may have application and maintenance records for multiple accepted rentals. The signed-in Profile view shows the account role and email and lets the user update their display name; role and email stay read-only.

The Flask backend is the working local MVP for the agreed flows, not a production identity or payments platform. Email verification, password reset, MFA, external payment collection, database backup, and hosted deployment still need separate work.
