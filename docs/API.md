# PropManager Backend API

Base path: `/api`. The current backend is a Flask JSON API backed by SQLite. All mutations require a valid `X-CSRF-Token` header matching the `pm_csrf` cookie. After sign-in, send cookies with requests (`credentials: same-origin` in the current Vite client).

## Roles

| Role | Access |
| --- | --- |
| `renter` | Browse available listings; create and view their own applications; create and view maintenance requests for accepted rentals. |
| `owner` | Create and edit own non-rented listings; view applications for own listings; accept or decline pending applications; view maintenance requests for own listings. |
| `broker` | View all applications and properties; view the full monthly commission ledger and update entry statuses; triage all maintenance tickets and add broker notes. |

Renter and owner accounts register through the public endpoint. Broker accounts are provisioned with the `create-broker` Flask CLI command. The server checks the role on every protected API route; a client-supplied role is never trusted.

## Authentication

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/auth/csrf` | Public | Creates/returns the CSRF token cookie and token value. |
| `POST` | `/auth/register` | CSRF | Create renter or owner account and sign in. Required: `name`, `email`, `password`, optional `role`. |
| `POST` | `/auth/login` | CSRF | Verify credentials and issue a server-checked session cookie. Required: `email`, `password`. |
| `GET` | `/auth/me` | Signed in | Return the authenticated account. |
| `PATCH` | `/auth/me` | CSRF + signed in | Update the account's display name. Email and role are read-only here. |
| `POST` | `/auth/logout` | CSRF | Revoke the current server-side session and clear its cookie. |
| `GET` | `/health` | Public | Return API health. |

Passwords are Argon2id hashes, not reversibly encrypted values. Session IDs are random opaque values; only their SHA-256 hashes are stored. Sessions expire after seven days. Cookies use `HttpOnly` and `SameSite=Lax`; `COOKIE_SECURE` defaults to `true` and should only be set to `false` for local HTTP development. HTTPS/TLS is required to protect credentials in transit in a hosted deployment. SQLite data-at-rest encryption is not configured in this prototype.

## Listings and applications

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| `GET` | `/properties` | Public / signed-in | Available listings for renters/public; own listings for owners; all listings for brokers. Supports `q`, `location`, `property_type`, `min_rent`, `max_rent` and `status` filters. Each row includes `available_units` and an optional `image_url`. |
| `POST` | `/properties` | Owner | Create a listing. Required: `title`, `address`, `monthly_rent`; optional: `property_type`, `description`, `unit_count`. Types: Apartment, PG/Hostel, Office/Commercial. |
| `PATCH` | `/properties/{id}` | Owner | Edit an owned listing and set it `Available` or `Unavailable`. Rented listings cannot be edited through this route. Accepts an optional `image_url`. |
| `GET` | `/properties/{id}/units` | Signed in | Unit/room inventory for a listing, including status and rent. |
| `POST` | `/properties/{id}/units` | Owner | Add a unit with a label and monthly rent. |
| `GET` | `/applications` | Signed in | Own applications for renters, own-property applications for owners, all applications for brokers. |
| `GET` | `/applications/{id}` | Signed in | Application detail with unit label and a chronological status-history timeline. |
| `POST` | `/applications` | Renter | Apply to an available listing. Required: `property_id`; optional: `message` and `unit_id`. Duplicate applications are rejected. A renter may have accepted applications for multiple properties. |
| `POST` | `/applications/{id}/decision` | Listing owner | Set a pending application to `Accepted` or `Declined`. Accepting assigns an available unit, records the decision, notifies the renter and brokers, and creates the first month's two charges. Several renters can be accepted for a multi-unit listing. |
| `POST` | `/applications/{id}/end` | Listing owner or broker | End the active rental; future monthly charges stop and the listing becomes available again. |
| `GET` | `/dashboard` | Signed in | Role-specific dashboard counts and `unread_notifications`. The broker summary includes properties, active rentals, pending applications, Pending/In Progress/Resolved/Skipped ticket counts, and the pending commission total. |

## Analytics

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/analytics` | Signed in | Role-scoped KPIs, chart series and raw tables. Renters see their own applications/rentals/issues/ledger; owners see their listings and tenant activity; brokers see portfolio-wide data, lead pipeline and organization counts. |

Chart series include applications by status and month, properties by type, tickets by status/priority/category/month, commission totals by month/status, and — for brokers — leads by status. The `monthly` array combines applications, issues and commission obligations per month. The `properties` array is the detailed table used by the optional "detailed tables" view.

## Notifications

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/notifications?limit=20` | Signed in | Recent in-app notifications for the current account and an `unread` count. |
| `PATCH` | `/notifications/{id}/read` | Signed in | Mark one notification as read. |
| `POST` | `/notifications/read-all` | Signed in | Mark all of the current account's notifications as read. |

Notifications are created for new applications, decisions, new issues, ticket status changes and ended rentals. They are in-app only; no email, SMS or WhatsApp is sent.

## Organizations (B2B)

A global `broker` account can access every organization. Other accounts must be a member with an organization role: `org_admin`, `manager`, `broker`, `accountant` or `technician`. `org_admin` and global brokers can manage members, invitations, commission terms and property links. All other members have read access to portfolio data.

| Method | Endpoint | Org role | Description |
| --- | --- | --- | --- |
| `GET` | `/orgs` | Member | Organizations the current user belongs to; global brokers see all. |
| `POST` | `/orgs` | Signed in | Create an organization; the creator becomes `org_admin`. Required: `name`; optional: `slug`. |
| `GET` | `/orgs/{id}` | Member | Organization detail and the current user's organization role. |
| `PATCH` | `/orgs/{id}` | `org_admin`, broker | Rename or change the slug. |
| `GET` | `/orgs/{id}/members` | Member | Team members and their roles. |
| `PATCH` | `/orgs/{id}/members/{user_id}` | `org_admin`, broker | Change a member's organization role. |
| `DELETE` | `/orgs/{id}/members/{user_id}` | `org_admin`, broker | Remove a member. |
| `GET` | `/orgs/{id}/invitations` | Member | Invitations and expiry/accepted state. |
| `POST` | `/orgs/{id}/invitations` | `org_admin`, broker | Invite by email and role. Returns a one-time token valid for seven days. |
| `POST` | `/orgs/invitations/{token}/accept` | Signed in | Accept with the invited email address; adds an `org_members` row. |
| `POST` | `/orgs/{id}/properties/{property_id}` | `org_admin`, broker, owning member | Link a listing to the portfolio. |
| `DELETE` | `/orgs/{id}/properties/{property_id}` | `org_admin`, broker | Unlink a listing. |
| `GET` | `/orgs/{id}/commission-terms` | Member | Custom commission rates by party and effective date. |
| `POST` | `/orgs/{id}/commission-terms` | `org_admin`, broker | Set a rate in basis points, optionally with `effective_from` (`YYYY-MM-DD`). |
| `GET` | `/orgs/{id}/leads` | Member | Owner/tenant leads. |
| `POST` | `/orgs/{id}/leads` | Member | Add a lead. Required: `name`, `email`. |
| `PATCH` | `/orgs/{id}/leads/{lead_id}` | Member | Update lead `status` and `notes`. |
| `GET` | `/orgs/{id}/dashboard` | Member | Portfolio rollup: properties, units, occupancy, rentals, applications, issues, pending commission and lead status counts. |
| `GET` | `/orgs/{id}/export.csv?type=...` | Member | CSV export for `commissions`, `properties`, `issues` or `leads`. Cells beginning with `=`, `+`, `-` or `@` are escaped against spreadsheet formula injection. |

Organization-role checks are **additional** to the account-role checks listed earlier: lead and property-link mutations also require an owner or broker account.

Commission generation uses an organization's active term for its linked properties; properties without an organization use the 10% default. Existing cycles keep the rate at which they were created.

## Commission ledger

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| `GET` | `/commissions` | Renter, owner, broker | List ledger entries. Renters see their own `renter` entries, owners see their `owner` entries, and brokers see both sides for all rentals. |
| `POST` | `/commissions/generate` | Broker | Idempotently generate charges for `billing_period` (`YYYY-MM`). |
| `PATCH` | `/commissions/{id}` | Broker | Set one renter/owner charge to `Pending`, `Paid` or `Waived`. |

Each billing month, both the renter and owner receive a separate ledger entry equal to 10% of monthly rent, stored in paise. Acceptance creates the first current-month entries. `GET /commissions` catches up the current month; `flask --app backend.app generate-commissions --month YYYY-MM` can be run by a monthly scheduler. Entries are not prorated and the app does not collect money.

## Maintenance tickets

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| `GET` | `/tickets` | Signed in | List tickets visible to the current renter, owner or broker. Includes `similar_issue_count` (other open reports at the same property and category), `similar_resident_count` (distinct residents behind those reports) and `age_hours`. Use `?sort=priority` for importance → resident impact → oldest-first ordering. |
| `GET` | `/tickets/{id}` | Signed in | Ticket detail with the same two counts and chronological event history; other users receive 404. |
| `POST` | `/tickets` | Renter | Create a request for an accepted rental. Required: `property_id`, `title`, `description`; optional: `category`, `priority`. |
| `PATCH` | `/tickets/{id}` | Broker | Set status to `Pending`, `In Progress`, `Resolved` or `Skipped`; add a `manager_note`. `Skipped` requires a non-empty reason (400 otherwise). Changes are written to ticket history. |

Categories: `Maintenance`, `Plumbing`, `Electrical`, `Appliance`, `Structural`, `Personal safety`, `Neighbourhood safety`, `Security/access`, `Cleanliness/facilities`, `Other`. Priorities: `Low`, `Medium`, `High`, `Urgent`. Similar-report and distinct-resident counts are advisory decision support; the backend does not automatically calculate a score or approve/skip tickets.

## Error responses

Errors use JSON: `{"error": "..."}`. Expected status codes include `400` for invalid input, `401` when signed out or credentials are invalid, `403` for role/CSRF restrictions, `404` for missing or inaccessible records, `409` for duplicate/conflicting records, and `429` after repeated failed sign-in attempts.
