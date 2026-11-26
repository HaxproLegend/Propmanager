# Legal approach — internal product note

**Status:** Working policy note, 26 November 2026. This is **not legal advice** and is not a substitute for review by qualified counsel. It records how PropManager intends to behave so the team can build consistently, and what still needs approved wording.

## 1. Posture

PropManager is a coordination tool, not a landlord, a payment processor, a legal adviser or a rule engine. The product should be **flexible where people need judgement** and **firm where people need clarity**.

That means:

- Brokers and owners keep operational discretion — they decide applications, move issues through their lifecycle, waive ledger entries and end rentals.
- Renters are never silently rejected, delayed, scored or charged. They see the same status timeline the broker sees, and adverse decisions carry a visible reason.
- Nothing in the app invents tenancy law, notice periods, deposit rules, tenant-benefit clauses or fee legality.

The goal is procedural fairness, not “favouring” one side. Both sides get predictability and an escape hatch.

## 2. Three layers

| Layer | What it is | Current handling |
| --- | --- | --- |
| Product workflow rules | How the app behaves | Human decisions only; status timelines; Skipped requires a reason; no automatic scoring, approval or delay. Advisory only. |
| Plain-language platform policy | Short, readable summary shown in-app and on the landing page | `How we handle issues & applications` page, linked from auth, the footer and the workspace sidebar. |
| Formal legal documents | Lease, tenant benefits, owner–broker agreement, commission agreement | Not written by the team yet. The app holds placeholders only; approved wording comes later with counsel review. |

## 3. Where we deliberately give leeway

| Area | Flexible behaviour | Guardrail that stays firm |
| --- | --- | --- |
| Application decisions | Owner accepts or declines; broker coordinates. | Declined applications can carry a short reason visible to the renter. No auto-decision. |
| Issue lifecycle | Broker can set any of Pending / In Progress / Resolved / Skipped. | Skipped requires a non-empty reason; full event history is visible to the reporter. |
| Overdue / urgency | Thresholds are advisory and can be configured per organization later. | No automatic penalty, delay or escalation. Similar-report and resident counts are decision support only. |
| Commission | Rate is 10% by default, configurable per organization, and entries can be marked Paid or Waived. | Never charged or collected in-app; generated idempotently by month, party and rental; disclosed before applying via an acknowledgement checkbox. |
| Ending a rental | Owner or broker can end it, with a reason recorded in the timeline. | Listing frees its unit; future commission cycles stop; renter and owner are notified. |
| Team permissions | Org admins can change member roles and link properties. | Global brokers can access all organizations; other users must be members. Account role is never trusted from the browser. |

## 4. What we deliberately do not do

- No auto-generated notices, eviction text, legal deadlines or “you owe this amount” demands.
- No jurisdiction-specific rent control, deposit caps or statutory notice periods encoded as rules.
- No identity documents, payment card collection, e-signature or document uploads in this prototype.
- No claims that commission entries are collected fees; they are ledger obligations only.
- No legal conclusions from the navigation assistant or analytics views.

## 5. Open decisions before any legal text is written

- Which jurisdiction(s) the brokerage operates in, and whether broker licensing or fee disclosure rules apply.
- Who supplies the approved lease and tenant-benefit wording.
- Whether commission terms need a signed acknowledgement per owner/property rather than a product checkbox.
- Whether declined-application reasons should be mandatory or optional (currently optional but recommended).
- Retention and deletion policy for personal data, and whether a formal privacy notice is required.
- Whether overdue thresholds should become per-org configuration in Phase 3.

## 6. Mapping to the current implementation

- `applications.decline_reason` + application event history → transparent decisions.
- Required `manager_note` on Skipped → visible reason for adverse issue outcomes.
- `commission_terms` per organization → configurable rates, with ledger-only generation.
- `GET /api/analytics` → numbers without legal conclusions.
- `docs/FEATURE_SCRIPT.md` → demo walkthrough that states the demo boundaries out loud.

## 7. Next steps

1. Keep this note internal; do not present it as customer-facing terms.
2. Get counsel to review the posture above before any real tenant or owner data is stored.
3. Add approved documents to a future per-property/per-org documents area, never invent text here.
4. Revisit the open decisions list before Phase 3/4 scope is locked.
