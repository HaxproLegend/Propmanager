# PropManager PRD status

The submitted PRD v1.2 described a browser-only maintenance demo with a Tenant/Property Manager role toggle and IndexedDB. The partner wireframes preserve that maintenance flow: request submission, renter request history, a manager board and a property directory.

The team has since selected the **brokerage MVP**: renters, owners and brokers share a real account system; owners publish listings and decide applications; brokers coordinate placements and maintenance; renters apply and submit maintenance requests after acceptance. The submitted PRD is the history and maintenance reference, not a complete description of this revised scope. The team should update the submitted PRD and seek mentor approval for the product/stack change.

## Implemented MVP in this repository

- React/Vite landing page, account creation and sign-in/out.
- Flask/SQLite persistence with Argon2id password hashes, database-checked opaque session cookies, CSRF checks and sign-in throttling.
- Server-assigned roles: renter and owner self-register; broker accounts are provisioned by the CLI.
- Owners create property listings and accept/decline renter applications.
- Renters browse available homes and apply. After acceptance, renters can create maintenance requests.
- Brokers see application records, maintain a manually entered placement-fee ledger, and manage the maintenance queue.
- Maintenance tickets include category and priority, property/priority/status filters, search, a similar-issue count, broker notes and statuses Pending, In Progress, Resolved or Skipped.
- Role-specific dashboard summaries include pending applications, work in progress, pending commissions and skipped tickets.

## Deliberately not implemented in this MVP

Real rent or commission processing, an agreed commission formula, broker-owner/renter messaging, verification email, password reset, MFA, technician/vendor management, image storage, notifications, automated AI triage, analytics beyond demo counts, audit trails, deployment, database backup and multi-broker assignment. These require product decisions or external services and remain future scope.

The two partner PDFs are planning references. The Good-to-Have list remains a prioritized backlog; a feature marked High is not automatically part of the current MVP.
