# PropManager — Brokerage MVP Product Requirements Document

**Document status:** Working PRD, updated 19 November 2026; mentor approval is pending for the scope change from the submitted PRD v1.2.
**Project:** PropManager rental brokerage and property operations platform
**Team:** Aranya Datta and Sayali Panchbhai

## 1. Product summary

PropManager is a broker-supported rental platform connecting renters with property owners. Owners can list and manage multiple properties. Renters can discover homes, apply, and manage more than one active rental. Brokers coordinate applications and rental issues through one role-aware operations dashboard. The MVP also records recurring brokerage commission entries for both sides of an active rental.

The product is designed to extend from individual rentals to PG/hostel and office/commercial buildings. The MVP demonstrates that model with property types and unit counts; it does not yet provide organization accounts, multi-broker teams, or payment processing.

## 2. Problem and opportunity

In the target brokerage workflow, owners and renters rely on a middle person to coordinate listings, applications, and follow-up issues. Those activities can become difficult to track across several properties, tenants, and buildings. PropManager brings the rental relationship and operational issue status into one place, with visibility controlled by each account’s role.

This problem framing is a product hypothesis. User interviews and mentor feedback should validate it before the team treats it as proven market evidence.

## 3. Goals and non-goals

### Goals

- Let renters browse available listings, apply, track their applications, and see their accepted rentals.
- Let owners create and manage multiple listings, review applications, and see relevant issues for their properties.
- Give brokers/managers one dashboard for placements, property operations, issue triage, and the commission ledger.
- Support apartment, PG/hostel, and office/commercial listing types with a unit or room count.
- Make issue importance, similar reports, and affected residents visible to support human prioritization.
- Record a recurring 10% monthly-rent commission entry for the renter and a separate 10% entry for the owner.
- Provide a profile page and enforce role-based access to account and property data.

### Non-goals for this MVP

- Collecting rent or commission, transferring funds, invoicing, or reconciling real payments.
- Defining or publishing legal lease text, tenant-benefit clauses, or legal advice. The team will provide approved wording later.
- Automatic approval or rejection of applications or issues.
- Numeric or AI-based issue scoring, automated emergency detection, or an automatic rule that delays lower-priority issues.
- Email/SMS/WhatsApp notifications, in-app chat, password reset, MFA, identity verification, or social login.
- Technician/vendor scheduling, work orders, photos, or repair-cost tracking.
- Organization-level accounts, multiple broker teams, or a separate platform administrator console.

## 4. Users and roles

The product uses one application and dashboard shell. The current authenticated role determines which navigation, records, and actions are available. Role selection is not a user-controlled security toggle; the server assigns and checks the role.

| Role | Main needs | Access and actions |
| --- | --- | --- |
| Renter | Find a place, apply, track rentals, report issues | Browse listings; manage own applications and accepted rentals; submit and view issues for own active rentals; update own profile |
| Owner | Publish and manage properties, decide applications, follow issues | Create/update own listings; review applications for own properties; see relevant rental and issue details; update own profile |
| Broker / Manager | Coordinate placements and service across properties | View and manage the brokerage-wide application workflow, issue queue, property/rental operations and commission ledger; update own profile |

There is no separate admin workspace in the MVP. Broker/Manager is the operational role. Self-registration is available to renters and owners; broker accounts are provisioned by the project operator.

## 5. Core features and requirements

Priority labels: **M** = must work for the MVP demo; **S** = should have if schedule allows; **C** = stretch.

### 5.1 Accounts, authentication and profile

- **FR-01 (M):** A renter or owner can register, sign in, and sign out using an email and password.
- **FR-02 (M):** Broker accounts are provisioned outside public self-registration.
- **FR-03 (M):** The system stores passwords as salted Argon2id hashes; it never stores reversible password encryption.
- **FR-04 (M):** Authenticated requests use server-checked sessions, CSRF protection for state-changing requests, and server-side role checks.
- **FR-05 (M):** A signed-in user can view and update their profile name. Email and role are read-only in the profile screen.
- **FR-06 (M):** Production deployment must use HTTPS/TLS. Encryption of the database file at rest is a deployment decision and is not claimed as implemented in the current MVP.

### 5.2 Property discovery and portfolio

- **FR-07 (M):** An owner can create, edit, mark available, and view multiple properties from “My Properties.”
- **FR-08 (M):** A listing records its name/address, property type, rent, unit/room count, availability, description, and owner.
- **FR-09 (M):** Supported property types are Apartment, PG/Hostel, and Office/Commercial.
- **FR-10 (M):** A renter can browse available listings and submit an application to a selected property.
- **FR-11 (M):** A renter can maintain applications and accepted rental records for multiple properties under one account.
- **FR-12 (S):** Search and filter listings by location, property type, price, and availability.

### 5.3 Rental applications and coordination

- **FR-13 (M):** Owners can view applications for their own listings and accept or decline them.
- **FR-14 (M):** Brokers can view and coordinate the application workflow across properties.
- **FR-15 (M):** The renter can see the application outcome and, if accepted, the rental in “My Properties.”
- **FR-16 (M):** An owner or broker can end an active rental; the listing then becomes available again.
- **FR-17 (S):** Show clear dates and status history for application and rental changes.

### 5.4 Issue reporting and broker priority queue

- **FR-18 (M):** A renter can submit an issue against one of their active rentals, choosing a category, importance, and description.
- **FR-19 (M):** Categories include Maintenance, Plumbing, Electrical, Appliance, Structural, Personal Safety, Neighbourhood Safety, Security/Access, Cleanliness/Facilities, and Other.
- **FR-20 (M):** An owner can see issues related to their property. Brokers/managers can see and manage the brokerage-wide issue queue.
- **FR-21 (M):** The broker queue supports statuses **Pending**, **In Progress**, **Resolved**, and **Skipped**. A skipped issue requires a reason visible in its history.
- **FR-22 (M):** The queue shows category, importance, property, status, submission time, number of similar open reports, and the number of distinct residents who submitted those matching reports. Matching means the same property and issue category; label this as a report count, not proof of a shared root cause.
- **FR-23 (M):** The broker can filter, search, sort, add an internal note, and change an issue status.
- **FR-24 (M):** Similar issue counts and resident impact are decision support only. The broker makes the priority decision; the system does not silently reject, approve, or delay an issue based on an automatic score.
- **FR-25 (S):** Keep a resident-visible status history and explain delays or skipped decisions in plain language.

### 5.5 Commission ledger

- **FR-26 (M):** For each accepted rental, the system records a separate monthly commission entry for the renter and for the owner.
- **FR-27 (M):** Each party’s commission is 10% of the rental’s monthly rent. The current demo calculates the full monthly amount and does not prorate partial months.
- **FR-28 (M):** Commission entries are recurring by billing month while the rental is active, are unique per rental/month/party, and can be marked Pending, Paid, or Waived by a broker.
- **FR-29 (M):** The broker dashboard shows the pending ledger total and commission entries by rental, month, party, amount, and status.
- **FR-30 (M):** The ledger records obligations only. No money is charged, transferred, or collected by the MVP.

### 5.6 Role-aware dashboard and navigation

- **FR-31 (M):** The same application shell presents role-appropriate dashboard content and navigation for renter, owner, or broker/manager.
- **FR-32 (M):** The renter dashboard summarizes applications, active rentals, issue updates, and that renter’s own monthly commission ledger entries.
- **FR-33 (M):** The owner dashboard summarizes owned properties, new applications, and open issue updates.
- **FR-34 (M):** The broker/manager dashboard summarizes properties, active rentals, pending commission totals, and counts for Pending, In Progress, Resolved, and Skipped issues.
- **FR-35 (M):** “My Properties” is available to owners for their listings and to renters for their accepted rentals.
- **FR-36 (M):** API authorization is enforced on every protected record operation; hiding a control in the UI alone is not sufficient.

## 6. Key user journeys

### Renter

1. Register/sign in and complete the profile name.
2. Search available listings and open a property detail.
3. Apply to a property and track the decision.
4. After acceptance, see the rental in “My Properties.” The renter may have more than one accepted rental.
5. Report an issue for an active rental, choose an issue type and importance, and follow status updates.
6. View the recurring commission ledger entry associated with the rental; no payment is processed in the MVP.

### Owner

1. Register/sign in and complete the profile name.
2. Create one or more listings, selecting apartment, PG/hostel, or office/commercial and the unit/room count.
3. Review applications for an owned listing and accept or decline them.
4. Follow active rentals and relevant issue updates from the owner dashboard.
5. View the owner-side recurring commission ledger entry for each active rental.

### Broker / Manager

1. Sign in to the operations dashboard.
2. Review applications across the brokerage and coordinate owner decisions.
3. Review the issue queue; use urgency, importance, similar reports, affected residents, and elapsed time to decide what to handle first.
4. Move issues through Pending, In Progress, Resolved, or Skipped; add a reason when skipping.
5. Review monthly commission entries for both sides and update ledger status.

## 7. Wireframe and screen requirements

The accompanying low-fidelity wireframe is `PropManager-Brokerage-Wireframe.svg` (PDF export: `PropManager-Brokerage-Wireframe.pdf`). It depicts three role views in one application shell.

- **Owner:** summary cards; multiple property cards; add/manage property actions; recent applications; issue updates; commission summary.
- **Renter:** listing search; recommended listings; “My Properties” for multiple leases; issue submission and issue history; ledger visibility; profile.
- **Broker/Manager:** operational summary; searchable/filterable priority queue; issue lifecycle and status reason; recurring commission ledger; profile.
- Use clear role labels, consistent navigation, accessible form labels, and responsive layouts. Do not expose another user’s private profile or unrelated applications/issues.

## 8. Data and persistence overview

Core records include users, properties, units, applications/rentals, application history, issues, issue history, notifications, and commission ledger cycles. A property belongs to an owner and holds one or more units; an application links a renter to a property and, on acceptance, to a unit; an accepted application represents an active rental; issues relate to that rental; commission cycles relate to the rental, billing month, and charged party.

The current implementation uses Flask APIs and SQLite persistence. The client uses React and Vite. Database migrations must preserve existing records when fields are added. The commission-cycle generator must be idempotent for a rental, month, and party.

## 9. Security, privacy and error handling

- Enforce role and record ownership checks in Flask APIs.
- Use Argon2id password hashing, server-side sessions, CSRF protection, and login throttling.
- Never place passwords, session secrets, or CSRF secrets in logs or client-side storage.
- Use HTTPS/TLS for any hosted deployment. The MVP does not claim database-at-rest encryption.
- Validate all user input on the server and render user-authored descriptions as text.
- Show clear loading, empty, success, and failure states. Do not discard form data after a recoverable request failure.
- Do not store real payment credentials or process money in this demo.

## 10. Acceptance criteria for demo

- **AC-01:** A renter and owner can register/sign in; a provisioned broker can sign in; each sees role-appropriate navigation.
- **AC-02:** A renter cannot use APIs to view or change another renter’s private records; an owner cannot manage another owner’s listings.
- **AC-03:** An owner creates two different property types and sees both in “My Properties.”
- **AC-04:** A renter applies to two properties, has both accepted, and sees both active rentals.
- **AC-05:** The owner can accept or decline an application; renter and broker see the resulting state.
- **AC-06:** A renter submits a Neighbourhood Safety or Personal Safety issue for an active rental.
- **AC-07:** The broker queue shows issue type, importance, matching open-report count, distinct reporting residents for those matches, and status.
- **AC-08:** The broker can move an issue to In Progress and Resolved; Skipped requires a reason; the dashboard counts statuses correctly.
- **AC-09:** An accepted rental generates two commission ledger entries for a month: 10% of monthly rent for the renter and 10% for the owner.
- **AC-10:** Re-running commission generation for the same month does not create duplicate entries; ending a rental stops future monthly entries.
- **AC-11:** The broker can mark a commission entry Pending, Paid, or Waived; no payment is actually processed.
- **AC-12:** A user can update their profile name; role and email remain read-only.
- **AC-13:** Invalid requests show a useful error and do not create partial records.
- **AC-14:** The screen adapts to a narrow viewport and keeps controls and labels readable.

## 11. Stretch features and later releases

These are excluded from the MVP unless the core acceptance criteria are complete and the team/mentor explicitly expands scope:

- Listing search filters and map view.
- Application/rental timeline and richer resident-visible issue history.
- Notifications, comments, image attachments, vendor assignment, repair cost tracking, and service-level deadlines.
- CSV/PDF reporting and operational analytics.
- ~~Organization accounts and building portfolios for PG operators or office-building businesses; multi-user broker teams and organization-level RBAC.~~ **Phase 2 (basic):** organizations, members, invitations, linked properties and per-organization commission terms are implemented. Full tenant isolation, multiple broker teams and organization-level administrator consoles remain later work.
- Payment gateway integration and automated commission collection, after legal and payment decisions.
- Accessibility preferences, language support, installable/offline mode, and additional deployment hardening.

## 12. Risks and open decisions

| Risk / open decision | Current handling |
| --- | --- |
| Brokerage commission terms and tenant benefits may need legal review | Model is only a demo ledger. Add tenant-benefit clauses only after the team supplies approved text and gets appropriate review. |
| 10% recurring charges may not suit all leases or jurisdictions | Treated as a project assumption for the demo, not legal or commercial advice. |
| Priority policy is not yet numerical | Broker uses visible factors and makes a human decision; no automated scoring. |
| “Skipped” may sound like an issue was ignored | Require a reason and expose the status clearly; revisit wording with users. |
| B2B growth could require organization-level isolation | Keep current single-broker dashboard simple; make organization and multi-broker support a later design decision. |
| Monthly commission generation needs reliable scheduling in deployment | Use an idempotent monthly job; local demo can invoke the generator manually or open the broker ledger for catch-up. |
| Database file encryption at rest is not configured | Do not claim it is implemented; decide and configure it before storing sensitive production data. |
| SQLite backups and hosted deployment | Use the `backup`/`restore` Flask CLI commands (online backup API, integrity-checked restore); schedule backups off-host and test restores. `vercel.mjs` takes the API origin from `API_ORIGIN`; cookies default to `COOKIE_SECURE=true`. See `docs/DEPLOYMENT.md`. |
| Demo data in a shared database | `seed-demo` is idempotent, identifiable by `@propmanager.demo` emails, and refuses hosted databases unless `--force` is given. It is for local presentations only. |
| Organization isolation | Phase 2 adds organization roles and member-scoped reads, but linked properties are visible through existing global listings APIs. True row-level tenancy and multi-broker team isolation require a later data-model change. |

## 13. Legal and approval note

This revised PRD supersedes the product scope described in submitted PRD v1.2 only after mentor/team approval. The submitted document remains a record of the original OJT proposal. The team will provide tenant-benefit and lease clause wording later; until then this PRD intentionally contains no invented legal clauses.
