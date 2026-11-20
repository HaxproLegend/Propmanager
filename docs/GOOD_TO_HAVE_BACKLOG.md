# Partner Good-to-Have Backlog

Companion reference: **PropManager Good-to-Have Features v1.1 (19 November 2026)**. These are proposed enhancements, not blanket MVP requirements. The current product decision is the broker-supported rental marketplace, with maintenance as one broker service workflow.

## Already represented in the current MVP

| Ref | Feature | Current implementation |
| --- | --- | --- |
| GF-01 | Filter by property and priority | Broker ticket filters |
| GF-02 | Sort and search | Ticket search; priority-first, then oldest-first ordering |
| GF-03 | Issue categories | Maintenance, Plumbing, Electrical, Appliance, Structural, Personal Safety, Neighbourhood Safety, Security/Access, Cleanliness/Facilities, Other |
| GF-06 | Manager notes | Broker note stored with ticket |
| GF-22 | Real login and role permissions | Flask-backed renter/owner/broker accounts and role-scoped APIs |
| GF-24 | Multi-property accounts | Owners manage multiple listings; renters can have multiple accepted rentals |
| GF-18 (partial) | Recurring-issue detection | Matching category/property counts are shown as a triage hint; no automated root-cause alert |

The brokerage MVP includes a broker-managed issue lifecycle (**Pending**, **In Progress**, **Resolved**, **Skipped**), with a reason required when an issue is skipped. Application decisions are separate from issue status. The commission ledger records a recurring 10% of monthly rent for each side of an accepted active rental; it does not collect money.

## Recommended next releases

### Release 1 — finish maintenance operations

- GF-04 overdue marker, after the team selects an overdue threshold.
- GF-05 ticket detail/status timeline and GF-23 audit history.
- GF-11 emergency escalation rule and a clear urgent-ticket path.
- GF-12 technician assignment and GF-13 visit scheduling, if a technician persona is in scope.

### Release 2 — tenant communication

- GF-08 status notifications; first decide email, SMS or WhatsApp and select a provider.
- GF-09 photo attachments; requires storage, upload constraints and privacy review.
- GF-10 ticket comments.

### Release 3 — operations insight

- GF-14 vendor directory, GF-15 repair cost tracking and GF-16 preventive maintenance.
- GF-19 service targets and GF-20 analytics after enough sample data exists.
- GF-21 renter rating after a ticket is resolved.
- GF-17 AI triage only after a human-reviewed baseline is agreed; never silently auto-approve emergencies.

### Release 4 — readiness and reach

- GF-25 hosted shared database, backup/restore and deployment hardening.
- GF-26 CSV/PDF export.
- GF-27 installable/offline experience, GF-28 language support, GF-29 voice input and GF-30 accessibility/dark-mode preferences.
- GF-07 bulk actions only if the broker queue grows large enough to justify them.

## Decisions still open

- Tenant-benefit and lease clauses: waiting for wording from the team; do not invent legal text.
- Priority scoring: importance, urgency, matching issue counts, and affected-resident count support a human broker decision. No numeric score or automatic delay/approval rule is set.
- Whether a future payment integration should collect the recurring ledger amounts; excluded from the MVP.
- Overdue threshold and emergency escalation criteria.
- Whether owners and renters communicate only through broker-visible status updates, or can exchange comments in the product.
- Organization accounts and multiple broker teams for B2B building portfolios.
