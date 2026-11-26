# PropManager

PropManager is a broker-supported rental service prototype with a B2C rental journey and a B2B brokerage workspace. It has a public landing page, server-backed renter/owner/broker accounts, searchable stock-image listings with unit inventory, applications with status timelines, broker-coordinated issue tickets with a visual priority queue, in-app notifications, a manual commission ledger, and organization portfolios with teams, invitations, per-organization commission terms, owner leads and CSV exports. A separate Analytics tab gives minimal charts plus detailed raw-number tables, and a navigation assistant opens screens or named records from plain-language requests. A `seed-demo` command loads realistic sample users, rentals, problems and an organization for presentations.

## Project layout

```text
Propmanager/
├── backend/                 Flask API, SQLite setup, and pytest suite
├── frontend/                React/Vite application
│   ├── src/                  Active workspace UI
│   │   ├── main.jsx            Auth, landing page, toasts and app entry
│   │   ├── Analytics.jsx       Charts, trends and detailed tables
│   │   ├── Assistant.jsx       Plain-language navigation assistant
│   │   ├── AppShell.jsx        Sidebar, topbar, notifications, quick navigation
│   │   ├── Dashboard.jsx       Role pages and data orchestration
│   │   ├── Listings.jsx        Search, stock-image cards and detail drawer
│   │   ├── BrokerQueue.jsx     Priority list and Kanban board
│   │   ├── Organizations.jsx   Portfolio health, teams, terms and leads
│   │   └── ui.jsx              Shared primitives (badges, drawer, timeline, toasts)
│   ├── legacy/               Original vanilla JS/CSS prototype kept for reference
│   ├── index.html            Vite entry page
│   ├── package.json          Frontend dependencies and scripts
│   └── vite.config.js        Local `/api` proxy
├── docs/                     API reference, PRD, wireframes, deployment and backup notes
├── .github/                  Backend CI workflow
├── .env.example              Local Flask environment template
├── vercel.mjs                Frontend build settings and configurable hosted API rewrite
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

3. Copy `.env.example` to `.env`. For local HTTP development, change `COOKIE_SECURE` to `false`; the default is `true` for hosted HTTPS deployments.
4. From the repository root, start Flask:

   ```sh
   python -m flask --app backend.app run
   ```

5. Open the Vite address shown in the frontend terminal (usually `http://localhost:5173`). Vite forwards `/api` requests to the local Flask API at `http://127.0.0.1:5000` by default. To use another API during frontend development, set `VITE_API_PROXY_TARGET` in `frontend/.env.local`.
6. For a populated demo, run `python -m flask --app backend.app seed-demo` from the repository root. This creates five sample accounts, eight stock-image listings with unit inventory, accepted rentals, applications in every state, realistic renter issues, notifications and commission entries. Use `seed-demo --reset` to recreate it.

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

Run `seed-demo`, then sign in with any of these accounts. The password for all demo accounts is `DemoPass123!`.

| Role | Email | What to look at |
| --- | --- | --- |
| Broker | `broker@propmanager.demo` | Priority queue with ranked issues, similar-report and resident counts, board view, bulk actions, full commission ledger, all organization portfolios |
| Owner | `owner@propmanager.demo` | Three property types, unit inventory, pending applications to accept, owner-side ledger, and the Northstar organization workspace |
| Renter A | `renter-a@propmanager.demo` | Accepted apartment rental, two reported issues with history, renter ledger, pending second application |
| Renter B | `renter-b@propmanager.demo` | PG room, urgent Personal Safety issue, declined application |
| Renter C | `renter-c@propmanager.demo` | Two active rentals, matching plumbing reports with Renter B, skipped issue with a reason |

A short walkthrough: sign in as the owner and accept the pending application; open **Organizations** to see portfolio health, the 9% owner term, an invitation and five leads; sign in as the broker and move the urgent issue to In Progress from the priority queue; sign in as Renter A and open the application timeline, issue history and ledger. The full script is in [docs/FEATURE_SCRIPT.md](docs/FEATURE_SCRIPT.md).

The commission is a ledger of obligations only. Its business formula and any real payment collection are intentionally undecided.

## Authentication in this version

- Passwords are hashed with Argon2id; this is one-way hashing, not reversible encryption. Use HTTPS/TLS when hosted to protect credentials in transit; SQLite disk encryption is not configured.
- The server issues random opaque session tokens, stores only their SHA-256 hashes, checks them on each signed-in request, and removes a token on sign-out.
- Session cookies are `HttpOnly` and `SameSite=Lax`; `COOKIE_SECURE` defaults to `true` and must stay `true` behind HTTPS. Use `false` only for local HTTP development.
- State-changing auth requests use a CSRF token. Sign-in failures are throttled after repeated attempts.
- Roles come from the server account record. The browser cannot grant itself broker access.

Use HTTPS in any shared or production deployment. `COOKIE_SECURE=false` is only for local HTTP development. This is an OJT prototype, not a production identity platform. Email verification, password reset, MFA, and administrator account management remain future work; do not claim these are implemented.

## Deployment

Vercel is configured in the repository-root `vercel.mjs` to install and build the app from `frontend/`, publish `frontend/dist`, and forward `/api/*` requests to the Flask API. Keep the Vercel project root set to the repository root. Set the Vercel environment variable `API_ORIGIN` to your API host origin (no trailing slash or `/api`); it replaces the hard-coded demo host. The full checklist is in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Backup and restore

The SQLite database can be backed up consistently while the app is running:

```sh
python -m flask --app backend.app backup
python -m flask --app backend.app backup --output /secure/path/propmanager-backup.sqlite3
python -m flask --app backend.app restore /secure/path/propmanager-backup.sqlite3 --yes
```

Backups are integrity-checked before a restore replaces the live database. Schedule them on the API host, keep copies off-host, encrypt them, and test restores. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the operational details.

## Scope notes

Each owner can manage multiple listings with unit-level inventory, and a renter may have application and maintenance records for multiple accepted rentals. The app shell keeps role-aware navigation, notifications and quick search available everywhere. Listings support keyword/location/type/rent/availability filters and a detail drawer with stock photos and unit selection. Applications and issues have visible timelines, and brokers must supply a reason before marking an issue Skipped. The priority queue is decision support only: importance, elapsed time, similar reports and distinct residents are shown, but the broker decides. The Analytics tab keeps charts minimal by default with detailed tables behind a toggle, and the assistant is a local rule-based navigator — it opens screens and named records but does not call an external AI service.

The Flask backend is the working local MVP for the agreed flows, not a production identity or payments platform. Backup commands and deployment configuration are provided, but the operator still needs to schedule backups, set `API_ORIGIN`/`COOKIE_SECURE` correctly, and arrange monitoring. Basic organization portfolios are implemented, but organization-level isolation, multiple broker teams and per-organization administrator consoles remain later work. Email verification, password reset, MFA, external payment collection and database-at-rest encryption are still future work.
