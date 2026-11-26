# Operations — Phase 3

This note covers the operations layer added in Phase 3 and what still has to be done by the deployed operator.

## 1. Organization tenancy and teams

- An organization has members with roles `org_admin`, `manager`, `broker`, `accountant` and `technician`. A single organization can contain several brokers and technicians; global broker accounts can serve every organization.
- Properties can be linked to an organization. Listings, applications, tickets and commission cycles are then visible to members of that organization in addition to a user's own records.
- Global brokers keep portfolio-wide visibility. Users without organization membership keep the original personal view.
- Assignment is per issue: a broker or org admin can assign an org member and a vendor, schedule a visit, record a repair cost and flag an issue as an emergency.

## 2. Service thresholds — advisory, never automatic

`GET/PATCH /api/orgs/{id}/settings` stores `overdue_hours` (default 48) and `escalation_hours` (default 72) per organization.

- `GET /api/tickets` adds `sla_due_at`, `escalation_at`, `is_overdue` and `is_escalated`.
- Overdue and escalation flags are visible in the broker priority queue. They **do not** change status, delay an issue, reject a renter or notify anyone automatically.
- Emergency is a manual flag set by a broker or org admin. There is no automatic emergency detection or scoring.

## 3. Vendors, visits, costs and photos

- `GET/POST /api/orgs/{id}/vendors` and `PATCH /api/orgs/{id}/vendors/{vendor_id}` manage a vendor directory per organization.
- `PATCH /api/tickets/{id}/operations` sets assignee, vendor, scheduled visit, repair cost in paise and the emergency flag. Each change writes an `operation` event to the ticket history.
- `POST /api/tickets/{id}/photos` stores a URL and caption only. Binary files are **not** uploaded to SQLite in this prototype.
- Photos are visible in the ticket detail drawer. Before real uploads, the team needs object storage, access controls, size/type limits and a privacy review; do not put personal photos into the demo database.

## 4. Audit log

- `audit_log` is append-only in the application; there is no endpoint to edit or delete events.
- `GET /api/orgs/{id}/audit` is member-readable and returns the latest events.
- Audited actions include application decisions, rental endings, ticket status changes, operations, photos, commission status changes, vendor changes and org settings changes.
- The audit log lives in the same SQLite file as application data. Off-host backup and retention are therefore essential; a separate immutable store is a later hardening step.

## 5. Backups and retention

Use the CLI commands; they use SQLite's online backup API and are consistent while the app is running.

```sh
# Daily backup with local pruning of timestamped backups older than 30 days
python -m flask --app backend.app backup \
  --output /secure/backup/propmanager-$(date +%Y%m%dT%H%M%SZ).backup.sqlite3 \
  --retention-days 30
```

Operational requirements:

- Schedule the command on the API host (cron, PythonAnywhere scheduled tasks, etc.).
- Copy the resulting files to **off-host** storage; retention on the API host alone is not a backup strategy.
- Keep at least 7 daily and 4 weekly copies. Encrypt them at rest and restrict access: they contain Argon2id hashes, personal data and the audit log.
- Test a restore quarterly on a separate machine using `flask --app backend.app restore <file>`. Stop the API before restoring.
- `GET /api/health` is a liveness check; `GET /api/health/ready` also checks database connectivity.

## 6. Postgres migration

SQLite is correct for the OJT demo and is still the local default. The application now also supports Postgres through `DATABASE_URL` (Neon or any Postgres host): `psycopg` is used with a sqlite3-shaped wrapper, `?` parameters are translated to `%s`, DDL is translated to identity columns, monthly analytics use `to_char(to_timestamp(...))`, and idempotent inserts use `ON CONFLICT DO NOTHING`. `sslmode=require` is added when absent.

What remains for a production cutover:

1. Add Alembic/Flask-Migrate so schema changes are versioned instead of recreated from `CREATE TABLE IF NOT EXISTS`.
2. Run a one-time export/import staging period; verify row counts, foreign keys, commission uniqueness, timelines and audit history.
3. Switch the API host to `DATABASE_URL` behind a deployment flag, run read traffic first, then writes.
4. Replace SQLite backup retention with Neon PITR / `pg_dump` schedules.
5. Load-test the pooled connection settings; Neon autosuspends on the free tier, so expect cold starts.

Local development and the automated tests still use SQLite. Postgres mode is implemented but has not been exercised against a live Neon database from this workspace.

## 7. Monitoring

- Log application errors and HTTP status codes at the reverse proxy or WSGI server.
- Alert on repeated 5xx responses, failed `/api/health/ready` checks, disk usage and backup job failure.
- Capture request IDs and audit event IDs in support tickets; do not log passwords, session tokens or CSRF tokens.

## 8. Notifications beyond the app

In-app notifications are implemented. Email, SMS and WhatsApp are deliberately deferred: the team must choose a provider, consent wording and delivery policy first. No external message is sent today.
