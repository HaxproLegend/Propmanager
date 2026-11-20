# PropManager Backend API

Base path: `/api`. The current backend is a Flask JSON API backed by SQLite. All mutations require a valid `X-CSRF-Token` header matching the `pm_csrf` cookie. After sign-in, send cookies with requests (`credentials: same-origin` in the current Vite client).

## Roles

| Role | Access |
| --- | --- |
| `renter` | Browse available listings; create and view their own applications; create and view maintenance requests for accepted rentals. |
| `owner` | Create and edit own non-rented listings; view applications for own listings; accept or decline pending applications; view maintenance requests for own listings. |
| `broker` | View all applications and properties; create/update placement-fee ledger entries; triage all maintenance tickets and add broker notes. |

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

Passwords are Argon2id hashes, not reversibly encrypted values. Session IDs are random opaque values; only their SHA-256 hashes are stored. Sessions expire after seven days. Cookies use `HttpOnly` and `SameSite=Lax`; enable `COOKIE_SECURE=true` behind HTTPS. HTTPS/TLS is required to protect credentials in transit in a hosted deployment. SQLite data-at-rest encryption is not configured in this prototype.

## Listings and applications

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| `GET` | `/properties` | Public / signed-in | Available listings for renters/public; own listings for owners; all listings for brokers. |
| `POST` | `/properties` | Owner | Create a listing. Required: `title`, `address`, `monthly_rent`; optional: `property_type`, `description`, `unit_count`. Types: Apartment, PG/Hostel, Office/Commercial. |
| `PATCH` | `/properties/{id}` | Owner | Edit an owned listing and set it `Available` or `Unavailable`. Rented listings cannot be edited through this route. |
| `GET` | `/applications` | Signed in | Own applications for renters, own-property applications for owners, all applications for brokers. |
| `POST` | `/applications` | Renter | Apply to an available listing. Required: `property_id`; optional: `message`. Duplicate applications are rejected. A renter may have accepted applications for multiple properties. |
| `POST` | `/applications/{id}/decision` | Listing owner | Set a pending application to `Accepted` or `Declined`. Accepting rents the listing, blocks further applications and creates the first month's two charges. A renter may lease multiple properties. |
| `POST` | `/applications/{id}/end` | Listing owner or broker | End the active rental; future monthly charges stop and the listing becomes available again. |
| `GET` | `/dashboard` | Signed in | Role-specific dashboard counts and pending commission total for brokers. |

## Commission ledger

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| `GET` | `/commissions` | Broker | List placement-fee ledger entries. |
| `POST` | `/commissions/generate` | Broker | Idempotently generate charges for `billing_period` (`YYYY-MM`). |
| `PATCH` | `/commissions/{id}` | Broker | Set one renter/owner charge to `Pending`, `Paid` or `Waived`. |

Each billing month, both the renter and owner receive a separate ledger entry equal to 10% of monthly rent, stored in paise. Acceptance creates the first current-month entries. `GET /commissions` catches up the current month; `flask --app backend.app generate-commissions --month YYYY-MM` can be run by a monthly scheduler. Entries are not prorated and the app does not collect money.

## Maintenance tickets

| Method | Endpoint | Role | Description |
| --- | --- | --- | --- |
| `GET` | `/tickets` | Signed in | List tickets visible to the current renter, owner or broker. Includes a count of similar open issues at the same property and category. |
| `GET` | `/tickets/{id}` | Signed in | Ticket detail and chronological event history; other users receive 404. |
| `POST` | `/tickets` | Renter | Create a request for an accepted rental. Required: `property_id`, `title`, `description`; optional: `category`, `priority`. |
| `PATCH` | `/tickets/{id}` | Broker | Set status to `Pending`, `In Progress`, `Resolved` or `Skipped`; add a `manager_note`. Changes are written to ticket history. |

Categories: `Maintenance`, `Plumbing`, `Electrical`, `Appliance`, `Structural`, `Personal safety`, `Neighbourhood safety`, `Security/access`, `Cleanliness/facilities`, `Other`. Priorities: `Low`, `Medium`, `High`, `Urgent`. Similar-issue counts are advisory; the backend does not automatically calculate a score or approve/skip tickets.

## Error responses

Errors use JSON: `{"error": "..."}`. Expected status codes include `400` for invalid input, `401` when signed out or credentials are invalid, `403` for role/CSRF restrictions, `404` for missing or inaccessible records, `409` for duplicate/conflicting records, and `429` after repeated failed sign-in attempts.
