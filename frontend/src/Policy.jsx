import React from 'react';
import { SectionTitle } from './ui.jsx';

const SECTIONS = [
  {
    title: 'Applications and decisions',
    text: 'Owners decide who to accept. Renters can see the decision and its history. When an application is declined, the owner can add a short reason so the renter is not left guessing. PropManager never accepts or rejects automatically.',
  },
  {
    title: 'Issues and maintenance',
    text: 'A renter reports an issue against an active rental. A broker reviews it and moves it through Pending, In Progress, Resolved or Skipped. If it is Skipped, a reason is required and visible in the history. Importance, age and similar reports are decision support only — there is no automatic score, delay or approval.',
  },
  {
    title: 'Commission entries',
    text: 'Accepted rentals create a monthly ledger entry for the renter and a separate one for the owner. The default is 10% of monthly rent, but a brokerage can set its own rate. These are records of an obligation only: PropManager does not collect, transfer or charge money, and entries can be marked Paid or Waived by a broker.',
  },
  {
    title: 'Accounts and access',
    text: 'Renters and owners can create accounts. Broker accounts are provisioned by the brokerage and are never offered through public sign-up. Each account only sees the records its role allows; the browser cannot grant itself extra access.',
  },
  {
    title: 'Your information',
    text: 'Passwords are stored as one-way Argon2id hashes, sessions are checked on the server, and state changes use CSRF protection. Please do not share passwords. This demo does not ask for identity documents, payment cards or signatures.',
  },
  {
    title: 'What this is not',
    text: 'This page is a plain-language product summary, not a lease, tenancy agreement, legal advice or a contract. Approved lease wording, tenant-benefit clauses and brokerage agreements will be supplied by the team and reviewed before they are used.',
  },
];

export default function Policy() {
  return <div className="policy-content">
    <div className="page-head"><div className="eyebrow">PROPMANAGER · PLAIN LANGUAGE</div><h1>How we handle the important things</h1><p>A short, readable summary. Flexible where people need judgement, firm where they need clarity.</p></div>
    <section className="dash-section"><SectionTitle title="Our approach" sub="No automatic legal decisions, no silent rejections, no money collected in-app." />
      <div className="policy-grid">{SECTIONS.map((section, index) => <article className="policy-card" key={section.title}><span className="policy-index">{String(index + 1).padStart(2, '0')}</span><h2>{section.title}</h2><p>{section.text}</p></article>)}</div>
    </section>
    <section className="dash-section"><SectionTitle title="Need the formal documents?" sub="They are not part of this prototype yet." /><p className="detail-description">Lease text, tenant-benefit clauses and brokerage agreements will be added only after the team supplies approved wording and gets appropriate review. Until then, treat everything in PropManager as a working demonstration.</p></section>
  </div>;
}
