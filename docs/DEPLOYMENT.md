# Hosting and backup

## Shape of the deployment

- **Frontend:** the Vite build is static and is published from `frontend/dist` on Vercel.
- **API:** the Flask app runs on a Python host (the current demo uses PythonAnywhere) and owns the SQLite file.
- **Browser:** talks only to the Vercel domain. `vercel.mjs` rewrites `/api/*` to the API host, so session cookies stay same-origin and no CORS setup is needed.

`vercel.mjs` replaces `vercel.json`: Vercel accepts only one configuration file, and the `.mjs` form lets the API origin come from an environment variable instead of being hard-coded.

## Frontend on Vercel

1. Import the repository. Keep the **project root at the repository root** (not `frontend/`).
2. The build settings come from `vercel.mjs`: install `npm --prefix frontend ci`, build `npm --prefix frontend run build`, publish `frontend/dist`.
3. Add a project environment variable:

   ```text
   API_ORIGIN=https://your-api-host.example
   ```

   Use the origin only — no trailing slash and no `/api` suffix. The default in `vercel.mjs` is the existing demo host, so set this explicitly for your own deployment.
4. Redeploy, then check `https://<your-site>/api/health`. It should return `{"status":"ok"}`.

## API host

Run the Flask app with Python 3.10+ and `backend/requirements.txt`. A PythonAnywhere-style WSGI entrypoint looks like this:

```python
import os
import sys
from pathlib import Path

ROOT = Path("/home/<user>/propmanager")
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_PATH", str(ROOT / "backend/instance/propmanager.sqlite3"))
os.environ["COOKIE_SECURE"] = "true"

from backend.app import app
```

Deployment checklist:

- `COOKIE_SECURE=true` and HTTPS only. The application default is now `true`; local HTTP development must opt out explicitly.
- `DATABASE_PATH` must point at a writable, persistent location. The SQLite file is the only durable store; nothing else should hold application state.
- Create the broker account outside public registration:

  ```sh
  python -m flask --app backend.app create-broker
  ```

- Schedule the monthly ledger job (PythonAnywhere scheduled tasks, cron, etc.):

  ```sh
  python -m flask --app backend.app generate-commissions
  ```

  The endpoint `POST /api/commissions/generate` is broker-only and idempotent, but a scheduler makes catch-up reliable. `GET /api/commissions` also catches up the current month.
- Do not expose the API host's other pages to end users; `/api/*` through the Vercel rewrite is the supported path.

## Hosted Postgres (Neon)

The app supports two database modes:

- **Local demo:** no `DATABASE_URL`; uses the SQLite file at `DATABASE_PATH`. This is what the tests and `seed-demo` use.
- **Hosted:** set `DATABASE_URL` to a Postgres connection string (for example a Neon pooled URL). The app then uses `psycopg` instead of SQLite and forces `sslmode=require` when the URL does not already specify it.

Deployment notes for Neon:

1. Install `backend/requirements.txt` — it now includes `psycopg[binary]`.
2. Set `DATABASE_URL` in the Flask host environment. Do **not** paste credentials into chat or commit them.
3. Keep `COOKIE_SECURE=true` and serve everything over HTTPS. Vercel should rewrite `/api/*` to this host via `API_ORIGIN` so session cookies stay same-origin.
4. On first boot the app creates the schema with Postgres-compatible DDL. Migrating existing SQLite rows is **not** automatic — use a one-time export/import or the plan in `docs/OPERATIONS.md`.
5. Use Neon's pooled connection string. The app opens a connection per request rather than holding one globally, which suits serverless Postgres cold starts.
6. SQLite `backup` and `restore` CLI commands are disabled in Postgres mode. Use Neon point-in-time recovery or `pg_dump`/`pg_restore`, and keep taking scheduled off-host copies.

## Demo data

For presentations, seed a **local** database with sample users, listings, units, rentals, issues, notifications, commission entries and a sample organization with team members, terms and leads:

```sh
python -m flask --app backend.app seed-demo
python -m flask --app backend.app seed-demo --reset
```

All demo accounts use the password `DemoPass123!`; see `docs/FEATURE_SCRIPT.md` for the walkthrough. The command refuses a hosted database where `COOKIE_SECURE=true` unless `--force` is passed, and it is idempotent so it cannot double-seed a database. Demo users are identifiable by `@propmanager.demo` email addresses and a "Demo data" badge appears in their workspace.

## Backups

Use the CLI commands; they use SQLite's online backup API, which is consistent even while the app is running. Do not copy the live database file with `cp` while writes are happening.

```sh
# Timestamped backup next to the database
python -m flask --app backend.app backup

# Explicit destination
python -m flask --app backend.app backup --output /secure/backup/propmanager-2026-11-26.sqlite3

# Restore (integrity-checked before it replaces the live database)
python -m flask --app backend.app restore /secure/backup/propmanager-2026-11-26.sqlite3 --yes
```

Operational guidance:

- Schedule a daily backup on the API host and copy the files somewhere off-host.
- Retain at least 7 daily and 4 weekly backups, and **test a restore** on a separate machine or path regularly. An untested backup is not a backup.
- Backups contain Argon2id password hashes, hashed session tokens, and personal rental data. Encrypt them at rest and restrict access.
- SQLite file-at-rest encryption is still not configured in this prototype. Decide on encrypted storage or a managed database before storing sensitive production data.
- Restoring replaces the live database; the CLI checks `PRAGMA integrity_check` first and prompts for confirmation unless `--yes` is passed. Stop the API process before a restore so no open connection writes to the file being replaced.

## Known limits

- Single-process SQLite: fine for an OJT demo, not for multiple concurrent workers or high write volume.
- No email verification, password reset, MFA, payments, or hosted identity service. See the PRD non-goals.
- The rewrite assumes the API host is reachable over HTTPS and that no `Domain` attribute is added to cookies.
