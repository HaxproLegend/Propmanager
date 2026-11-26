# PropManager Feature Script

**Purpose:** 3–4 minute walkthrough of the brokerage MVP and its three role-based views.  
**Setup:** From the repository root run `python -m flask --app backend.app seed-demo`, start Flask and the Vite dev server, then sign in with any demo account below. Password for all demo accounts: `DemoPass123!`.

| Role | Email |
| --- | --- |
| Broker / Manager | `broker@propmanager.demo` |
| Owner | `owner@propmanager.demo` |
| Renter A | `renter-a@propmanager.demo` |
| Renter B | `renter-b@propmanager.demo` |
| Renter C | `renter-c@propmanager.demo` |

The sample data includes eight stock-image listings across apartments, PG/hostel rooms and offices, unit-level inventory, four accepted rentals, applications in Pending/Declined states, nine realistic issues across all four statuses, notifications and two months of commission entries.

## Opening

"PropManager is a rental brokerage and property operations platform. It brings renters, property owners and brokers into one application. Owners manage multiple properties and units, renters can hold more than one active rental, and brokers coordinate applications and reported issues from a shared operations dashboard. Each account sees only the tools and records allowed by its role."

## Owner view — 45 seconds

Sign in as `owner@propmanager.demo`.

"As an owner, I can see my portfolio at a glance. My Listings has search and filters by location, type, rent and availability. Opening a listing shows its stock photo and every unit or room with its status — one apartment has four flats with one already rented, and the PG has six rooms, so the same workflow covers an apartment building, a hostel or an office floor.

The Applications page has a pending application from Renter A. I can accept it. That assigns an available unit, adds a decision to the application timeline, and notifies the renter and the broker. The commission ledger is visible on the owner side too."

## Organization workspace — 45 seconds

Still signed in as the owner, open **Organizations**.

"Northstar Property Partners is the B2B layer. Portfolio health shows four linked properties, 18 units, 22% occupancy and the pending commission total. The team view has members and a pending manager invitation; owners and brokers can invite teammates and change organization roles. Commission terms show a custom 9% owner rate while the renter side stays at the 10% default — future monthly cycles for linked properties use these terms. Owner leads are a lightweight CRM, and each view can be exported as CSV for accounting or reporting."

## Renter view — 60 seconds

Sign in as `renter-a@propmanager.demo`.

"As a renter, Browse Homes has filters and a detail drawer with photos and units. I have one accepted rental at Lavender Apartments and a pending second application. Opening the application timeline shows when I applied and when the owner accepted.

In My Issues I can report a problem for my active rental and choose a category and importance. I already have a plumbing issue pending and a lift issue in progress with a broker note. The status history button shows every change in plain language, and the Commission page shows my monthly 10% ledger entry. No payment is collected here."

Sign in as `renter-b@propmanager.demo` and `renter-c@propmanager.demo` to show two different residents reporting plumbing problems at the same PG — the broker queue uses those as decision support.

## Broker / Manager view — 60 seconds

Sign in as `broker@propmanager.demo`.

"As a broker, I use one operations dashboard. The Priority Queue ranks open issues by importance, then resident impact, then how long they have been open. Each row shows similar open reports and the number of distinct residents behind them, plus elapsed time — these guide my decision, but the system never auto-approves, auto-delays or scores an issue.

I can switch to the Board view to see Pending, In Progress, Resolved and Skipped columns, filter and search, add a broker note, and change status. Skipping requires a reason. I can also select several issues and apply a bulk status change. Notifications in the top bar show new applications and issues."

## Commission explanation — 30 seconds

"For the demo, each accepted rental creates a monthly ledger entry equal to 10% of rent for the renter and a separate 10% for the owner, by billing month. The sample data includes paid, waived and pending examples. Entries are obligations only: the MVP does not collect or transfer money, and amounts are not prorated."

## Analytics and assistant — 30 seconds

"Every role has an Analytics tab. The default view is deliberately minimal: a few KPIs, small charts for applications, issues, property mix and commission by month. The detailed toggle reveals raw monthly and per-property tables and plain definitions of each number. The star button opens a navigation assistant — I can say 'show urgent issues' or 'open Lavender Apartments' and it opens that screen or drawer for me. It is a local rule-based helper, not an external AI service."

## Security and closing — 30 seconds

"The plain-language 'How we handle issues & applications' page explains the posture: flexible where people need judgement, firm where they need clarity. Owners can add a reason when declining, renters acknowledge that commission entries are ledger records, and no legal clause is invented in the app. Role checks are enforced in the Flask APIs, not only in the interface. Passwords use Argon2id hashing, sessions are server-checked opaque tokens, cookies are HttpOnly with SameSite, CSRF tokens protect changes, and failed sign-ins are throttled. The app uses HTTPS-ready secure cookies by default; database encryption at rest and hosted identity features are still future work."

## Feature scope at a glance

**Core MVP:** renter/owner/broker accounts; profile; searchable stock-image listings with unit inventory; multiple listings and rentals; applications with timelines; issue reporting with categories, history and notifications; broker priority list and board with notes, filters and Skipped reasons; recurring 10% ledger entries for both sides.

**B2B phase 2:** organization portfolios, team roles and invitations, linked properties, per-organization commission terms, owner leads, portfolio health and CSV exports.

**Navigation and insight:** role-scoped Analytics with minimal charts and detailed tables, plus a plain-language navigation assistant for screens and named records.

**Later releases:** organization-level isolation with multiple broker teams, payments, legal lease wording, technician assignment, notifications by email/SMS, comments and photos, AI-assisted triage after a human-reviewed baseline, and richer analytics.
