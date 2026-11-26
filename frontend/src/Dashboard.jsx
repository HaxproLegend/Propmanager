import React, { useCallback, useEffect, useState } from 'react';
import Analytics from './Analytics.jsx';
import Assistant from './Assistant.jsx';
import BrokerQueue from './BrokerQueue.jsx';
import ListingExplorer, { CompactListingGrid } from './Listings.jsx';
import Organizations from './Organizations.jsx';
import Policy from './Policy.jsx';
import { ApplicationEventLabel, Badge, Drawer, Empty, SectionTitle, Skeleton, Stats, Timeline, date, dateTime, label, money } from './ui.jsx';

export default function Dashboard({ user, request, page, setPage, notify, onChanged, onUpdateUser }) {
  const [properties, setProperties] = useState([]);
  const [applications, setApplications] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [commissions, setCommissions] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [focusListing, setFocusListing] = useState(null);
  const [ticketDetailId, setTicketDetailId] = useState(null);
  const [ticketDetail, setTicketDetail] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, a, t, c, s] = await Promise.all([
        request('/api/properties'), request('/api/applications'), request('/api/tickets?sort=priority'),
        request('/api/commissions'), request('/api/dashboard'),
      ]);
      setProperties(p.properties); setApplications(a.applications); setTickets(t.tickets);
      setCommissions(c.commissions); setSummary(s.summary);
    } catch (err) { notify(err.message, 'error'); }
    finally { setLoading(false); }
  }, [request, notify]);

  useEffect(() => { load(); }, [load]);

  const act = async (operation, message) => {
    setBusy(true);
    try { await operation(); await load(); notify(message); onChanged?.(); }
    catch (err) { notify(err.message, 'error'); }
    finally { setBusy(false); }
  };

  const openApplication = async (id) => {
    setDetailId(id); setDetail(null);
    try { const data = await request(`/api/applications/${id}`); setDetail(data); }
    catch (err) { notify(err.message, 'error'); setDetailId(null); }
  };

  const openTicket = async (id) => {
    setTicketDetailId(id); setTicketDetail(null);
    try { const data = await request(`/api/tickets/${id}`); setTicketDetail(data); }
    catch (err) { notify(err.message, 'error'); setTicketDetailId(null); }
  };

  const handleAssistantCommand = (intent) => {
    if (intent.kind === 'page' || intent.page) setPage(intent.page);
    if (intent.kind === 'listing') { setFocusListing({ id: intent.id, nonce: Date.now() }); setPage('listings'); }
    if (intent.kind === 'application') { setPage('applications'); openApplication(intent.id); }
    if (intent.kind === 'ticket') { setPage('issues'); openTicket(intent.id); }
    if (intent.kind === 'notifications') notify('Notifications are in the bell at the top of the workspace.');
  };

  const accepted = applications.filter((row) => row.status === 'Accepted');
  const pending = applications.filter((row) => row.status === 'Pending');
  const openIssues = tickets.filter((row) => !['Resolved', 'Skipped'].includes(row.status));
  const count = (key, fallback) => summary[key] ?? fallback;

  if (loading) return <div className="workspace"><Skeleton count={4} /></div>;

  return <div className="workspace">
    {page === 'profile' && <Profile user={user} request={request} act={act} busy={busy} onUpdateUser={onUpdateUser} />}

    {page === 'workspace' && <>
      <div className="page-head"><div className="eyebrow">PROPMANAGER · {label(user.role).toUpperCase()}</div><h1>Good to see you, {user.name.split(' ')[0]}.</h1><p>Keep rental details and maintenance moving in one place.</p></div>
      {user.role === 'renter' && <Stats items={[['Available homes', properties.length], ['My applications', applications.length], ['Active rentals', accepted.length], ['Open issues', openIssues.length]]} />}
      {user.role === 'owner' && <Stats items={[['My listings', properties.length], ['Pending applications', pending.length], ['Active rentals', accepted.length], ['Open issues', openIssues.length]]} />}
      {user.role === 'broker' && <Stats items={[
        ['Properties', count('properties', properties.length)],
        ['Active rentals', count('active_rentals', accepted.length)],
        ['Pending applications', pending.length],
        ['Pending commission', money((count('pending_commission_amount_paise', 0)) / 100)],
        ['Pending issues', count('pending_tickets', openIssues.length)],
        ['In progress', count('in_progress_tickets', 0)],
        ['Resolved', count('resolved_tickets', 0)],
        ['Skipped', count('skipped_tickets', 0)],
      ]} />}
      <CompactListingGrid properties={properties.slice(0, 3)} title={user.role === 'renter' ? 'Recently listed' : 'Portfolio snapshot'} sub="Open Browse homes to search, filter and see unit-level details." />
      <IssueSummary tickets={tickets.slice(0, 4)} />
    </>}

    {page === 'listings' && <ListingExplorer properties={properties} applications={applications} request={request} act={act} busy={busy} notify={notify} ownerMode={user.role !== 'renter'} onChanged={onChanged} focus={focusListing} />}

    {page === 'applications' && <ApplicationsPage applications={applications} user={user} request={request} act={act} busy={busy} onOpen={openApplication} />}

    {page === 'issues' && (user.role === 'broker'
      ? <BrokerQueue tickets={tickets} properties={properties} request={request} act={act} busy={busy} notify={notify} />
      : <IssuePage tickets={tickets} accepted={accepted} properties={properties} request={request} act={act} busy={busy} />)}

    {page === 'ledger' && <LedgerPage commissions={commissions} user={user} request={request} act={act} busy={busy} />}

    {page === 'analytics' && <Analytics user={user} request={request} notify={notify} />}

    {page === 'organizations' && <Organizations user={user} request={request} act={act} busy={busy} notify={notify} properties={properties} />}

    {page === 'policy' && <Policy />}

    <Drawer open={Boolean(detailId)} onClose={() => { setDetailId(null); setDetail(null); }} title={detail?.application?.property_title || 'Application'} sub={detail?.application ? `${detail.application.status} · ${money(detail.application.monthly_rent)} / month` : ''} wide>
      {detail && <>
        <div className="detail-meta"><Badge value={detail.application.status} />{detail.application.unit_label && <span>Unit: {detail.application.unit_label}</span>}<span>Applied {date(detail.application.created_at)}</span></div>
        <p className="detail-description">{detail.application.address} · {detail.application.owner_name} → {detail.application.renter_name}</p>
        <SectionTitle title="Status history" sub="Every decision is visible to the people involved." />
        <Timeline events={detail.history} describe={ApplicationEventLabel} empty="No updates recorded yet." />
      </>}
      {!detail && <Skeleton count={2} />}
    </Drawer>

    <Drawer open={Boolean(ticketDetailId)} onClose={() => { setTicketDetailId(null); setTicketDetail(null); }} title={ticketDetail?.ticket?.title || 'Issue'} sub={ticketDetail?.ticket ? `${ticketDetail.ticket.property_title} · ${ticketDetail.ticket.category}` : ''} wide>
      {ticketDetail && <>
        <div className="detail-meta"><Badge value={ticketDetail.ticket.priority} /><Badge value={ticketDetail.ticket.status} /><span>{dateTime(ticketDetail.ticket.created_at)}</span></div>
        <p className="detail-description">{ticketDetail.ticket.description}</p>
        {ticketDetail.ticket.manager_note && <p className="manager-note">Broker note: {ticketDetail.ticket.manager_note}</p>}
        <SectionTitle title="Status history" sub="Every change is visible to the reporter." />
        <Timeline events={ticketDetail.history} describe={(event) => event.event_type === 'created' ? 'Issue submitted' : event.event_type === 'note_updated' ? 'Broker note updated' : `Status changed to ${event.new_status || 'Pending'}`} />
      </>}
      {!ticketDetail && <Skeleton count={2} />}
    </Drawer>

    <Assistant user={user} context={{ properties, applications, tickets }} onCommand={handleAssistantCommand} />
  </div>;
}

function Profile({ user, request, act, busy, onUpdateUser }) {
  return <div className="page-head profile-page"><div className="eyebrow">ACCOUNT SETTINGS</div><h1>Your profile</h1><p>Your role is assigned by PropManager and cannot be changed here.</p>
    <form className="auth-panel profile-form" onSubmit={(event) => {
      event.preventDefault();
      const name = new FormData(event.currentTarget).get('name');
      act(async () => { const result = await request('/api/auth/me', { method: 'PATCH', body: JSON.stringify({ name }) }); onUpdateUser(result.user); }, 'Profile updated.');
    }}>
      <label className="form-field">Full name<input name="name" required minLength="2" maxLength="80" defaultValue={user.name} /></label>
      <label className="form-field">Email address<input value={user.email} readOnly /></label>
      <label className="form-field">Account role<input value={label(user.role)} readOnly /></label>
      <label className="form-field">Member since<input value={date(user.created_at)} readOnly /></label>
      <button className="button button-dark" disabled={busy}>Save profile →</button>
    </form>
  </div>;
}

function ApplicationsPage({ applications, user, request, act, busy, onOpen }) {
  return <section className="dash-section"><SectionTitle title="Applications" sub="Track decisions and rental history in one timeline." />
    {applications.length ? <div className="list-table">{applications.map((row) => <div className="data-row application-row" key={row.id}>
      <div><strong>{row.property_title}</strong><small>{money(row.monthly_rent)} / month · applied {date(row.created_at)}{row.unit_label ? ` · ${row.unit_label}` : ''}</small>{row.message && <p>{row.message}</p>}{row.decline_reason && <p className="decline-reason">Reason: {row.decline_reason}</p>}</div>
      <div className="row-actions"><Badge value={row.status} /><button className="button button-light" onClick={() => onOpen(row.id)}>Timeline</button>
        {user.role === 'owner' && row.status === 'Pending' && <>
          <button className="button button-dark" disabled={busy} onClick={() => act(() => request(`/api/applications/${row.id}/decision`, { method: 'POST', body: JSON.stringify({ status: 'Accepted' }) }), 'Application accepted.')}>Accept</button>
          <input aria-label="Reason for decline" className="decline-input" maxLength="500" id={`decline-${row.id}`} placeholder="Reason (shared with renter)" />
          <button className="button button-light" disabled={busy} onClick={() => { const reason = document.getElementById(`decline-${row.id}`)?.value || ''; act(() => request(`/api/applications/${row.id}/decision`, { method: 'POST', body: JSON.stringify({ status: 'Declined', reason }) }), 'Application declined.'); }}>Decline</button>
        </>}
        {(user.role === 'owner' || user.role === 'broker') && row.status === 'Accepted' && <button className="button button-light" disabled={busy} onClick={() => act(() => request(`/api/applications/${row.id}/end`, { method: 'POST', body: JSON.stringify({ reason: 'Rental ended from the workspace.' }) }), 'Rental ended.')}>End rental</button>}
      </div>
    </div>)}</div> : <Empty text="Applications will appear here." />}
  </section>;
}

function IssueSummary({ tickets }) {
  return <section className="dash-section"><SectionTitle title="Recent issues" sub="The priority queue has the full visual triage view." />{tickets.length ? <div className="list-table">{tickets.map((ticket) => <div className="data-row" key={ticket.id}><div><strong>{ticket.title}</strong><small>{ticket.property_title} · {ticket.category} · {ticket.priority}</small></div><div className="row-actions"><Badge value={ticket.status} />{ticket.similar_resident_count > 0 && <small>{ticket.similar_resident_count} resident(s)</small>}</div></div>)}</div> : <Empty text="No issues reported yet." />}</section>;
}

function IssuePage({ tickets, accepted, properties, request, act, busy }) {
  return <>
    <section className="dash-section"><SectionTitle title="Report an issue" sub="Maintenance, personal safety, neighbourhood concerns and more." />
      {accepted.length ? <form className="compact-form" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const data = Object.fromEntries(new FormData(form)); act(async () => { await request('/api/tickets', { method: 'POST', body: JSON.stringify(data) }); form.reset(); }, 'Issue submitted to the broker.'); }}>
        <label className="form-field">Rental<select name="property_id" required>{accepted.map((row) => <option value={row.property_id} key={row.id}>{row.property_title}{row.unit_label ? ` · ${row.unit_label}` : ''}</option>)}</select></label>
        <label className="form-field">Issue title<input name="title" required minLength="3" maxLength="100" /></label>
        <div className="form-pair"><label className="form-field">Category<select name="category">{['Maintenance','Plumbing','Electrical','Appliance','Structural','Personal safety','Neighbourhood safety','Security/access','Cleanliness/facilities','Other'].map((item) => <option key={item}>{item}</option>)}</select></label><label className="form-field">Importance<select name="priority">{['Low','Medium','High','Urgent'].map((item) => <option key={item}>{item}</option>)}</select></label></div>
        <label className="form-field">Describe the issue<textarea name="description" required minLength="5" maxLength="1000" rows="3" /></label>
        <button className="button button-dark" disabled={busy}>Submit issue →</button>
      </form> : <Empty text="After an owner accepts your application, you can report issues here." />}
    </section>
    <IssueSummary tickets={tickets} />
  </>;
}

function LedgerPage({ commissions, user, request, act, busy }) {
  const total = commissions.filter((row) => row.status === 'Pending').reduce((sum, row) => sum + row.amount_paise, 0);
  const pct = (bps) => `${(Number(bps || 1000) / 100).toFixed(Number(bps || 1000) % 100 ? 2 : 0)}%`;
  return <section className="dash-section"><SectionTitle title="Monthly commission ledger" sub="Rates follow organization terms when set, otherwise 10% per side. Ledger records only — no money is collected in-app." />
    <div className="ledger-total"><span>Pending total</span><strong>{money(total / 100)}</strong></div>
    {commissions.length ? <div className="list-table">{commissions.map((row) => <div className="data-row" key={row.id}>
      <div><strong>{row.property_title} · {row.party === 'renter' ? row.renter_name : row.owner_name}</strong><small>{row.billing_period} · {row.party} · {pct(row.rate_basis_points)} of {money(row.monthly_rent)} rent</small></div>
      <b>{money(row.amount_paise / 100)}</b>
      {user.role === 'broker' ? <select aria-label="Commission status" value={row.status} disabled={busy} onChange={(event) => act(() => request(`/api/commissions/${row.id}`, { method: 'PATCH', body: JSON.stringify({ status: event.target.value }) }), 'Commission status updated.')}>{['Pending','Paid','Waived'].map((status) => <option key={status}>{status}</option>)}</select> : <Badge value={row.status} />}
    </div>)}</div> : <Empty text="Commission entries appear after an application is accepted." />}
  </section>;
}
