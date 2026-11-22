import React, { useCallback, useEffect, useMemo, useState } from 'react';

const money = (value) => `₹${Number(value || 0).toLocaleString('en-IN')}`;
const date = (seconds) => new Date(seconds * 1000).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
const statusClass = (value) => value.toLowerCase().replaceAll(' ', '-');

export default function Dashboard({ user, request, onUpdateUser, onSignOut }) {
  const [properties, setProperties] = useState([]);
  const [applications, setApplications] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [commissions, setCommissions] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState('workspace');
  const [filter, setFilter] = useState({ status: 'All', priority: 'All', property: 'All', search: '' });

  const load = useCallback(async () => {
    setError('');
    try {
      const [p, a, t, c] = await Promise.all([
        request('/api/properties'), request('/api/applications'), request('/api/tickets'),
        user.role === 'broker' ? request('/api/commissions') : Promise.resolve({ commissions: [] }),
      ]);
      setProperties(p.properties); setApplications(a.applications); setTickets(t.tickets); setCommissions(c.commissions);
    } catch (err) { setError(err.message); }
  }, [request, user.role]);

  useEffect(() => { load(); }, [load]);
  const act = async (operation, message) => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); await load(); setNotice(message); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const accepted = applications.filter((a) => a.status === 'Accepted');
  const pendingApps = applications.filter((a) => a.status === 'Pending');
  const filteredTickets = useMemo(() => tickets.filter((t) =>
    (filter.status === 'All' || t.status === filter.status) &&
    (filter.priority === 'All' || t.priority === filter.priority) &&
    (filter.property === 'All' || String(t.property_id) === filter.property) &&
    `${t.title} ${t.property_title} ${t.renter_name} ${t.category}`.toLowerCase().includes(filter.search.toLowerCase())
  ).sort((a, b) => priorityRank(b.priority) - priorityRank(a.priority) || a.created_at - b.created_at), [tickets, filter]);

  return <main className="dashboard-page">
    <div className="dashboard-head"><div><div className="eyebrow">PROPMANAGER WORKSPACE · {label(user.role).toUpperCase()}</div><h1>{page === 'profile' ? 'Your profile' : `Good to see you, ${user.name.split(' ')[0]}.`}</h1><p>{page === 'profile' ? 'Manage your account details.' : 'Keep rental details and maintenance moving in one place.'}</p></div><div className="dashboard-head-actions"><button className="button button-light" onClick={() => setPage(page === 'profile' ? 'workspace' : 'profile')}>{page === 'profile' ? 'Back to workspace' : 'Profile'}</button><button className="button button-light" onClick={onSignOut}>Sign out</button></div></div>
    {error && <div className="dashboard-alert error" role="alert">{error}</div>}{notice && <div className="dashboard-alert" role="status">{notice}</div>}
    {page === 'profile' ? <Profile user={user} request={request} act={act} busy={busy} onUpdateUser={onUpdateUser} /> : user.role === 'renter' && <Renter user={user} properties={properties} applications={applications} tickets={tickets} request={request} act={act} busy={busy} />}
    {page === 'workspace' && user.role === 'owner' && <Owner properties={properties} applications={applications} tickets={tickets} request={request} act={act} busy={busy} />}
    {page === 'workspace' && user.role === 'broker' && <Broker properties={properties} applications={applications} pendingApps={pendingApps} accepted={accepted} tickets={filteredTickets} allTickets={tickets} commissions={commissions} filter={filter} setFilter={setFilter} request={request} act={act} busy={busy} />}
  </main>;
}

function Profile({ user, request, act, busy, onUpdateUser }) {
  return <section className="dash-section profile-panel"><SectionTitle title="Account details" sub="Your role is assigned by PropManager and cannot be changed here." /><form onSubmit={(e) => { e.preventDefault(); const name = new FormData(e.currentTarget).get('name'); act(async () => { const result = await request('/api/auth/me', { method: 'PATCH', body: JSON.stringify({ name }) }); onUpdateUser(result.user); }, 'Profile updated.'); }}><label className="form-field">Full name<input name="name" required minLength="2" maxLength="80" defaultValue={user.name} /></label><label className="form-field">Email address<input value={user.email} readOnly /></label><label className="form-field">Account role<input value={label(user.role)} readOnly /></label><label className="form-field">Member since<input value={user.created_at ? new Date(user.created_at * 1000).toLocaleDateString('en-IN') : '—'} readOnly /></label><button className="button button-dark" disabled={busy}>Save profile →</button></form></section>;
}

function Renter({ properties, applications, tickets, request, act, busy }) {
  const occupied = applications.filter((a) => a.status === 'Accepted');
  return <>
    <Stats items={[["Available homes", properties.length], ["My applications", applications.length], ["Open requests", tickets.filter((t) => t.status !== 'Resolved' && t.status !== 'Skipped').length]]} />
    <section className="dash-section"><SectionTitle title="My Properties" sub="Your accepted rentals across homes, PGs and office buildings." />{occupied.length ? <div className="listing-grid">{occupied.map((a) => <article className="my-property" key={a.id}><div className="my-property-type">{a.property_type || 'Property'}</div><h3>{a.property_title}</h3><p>{a.address}</p><div className="listing-rent">{money(a.monthly_rent)} <small>/ month</small></div><Badge value="Rented" /></article>)}</div> : <Empty text="Properties you lease will appear here after an owner accepts your application." />}</section>
    <section className="dash-section"><SectionTitle title="Homes available" sub="Browse owner listings and apply through PropManager." />
      <div className="listing-grid">{properties.length ? properties.map((p) => <article className="listing-card" key={p.id}><div className="listing-art"><span>⌂</span><small>{p.property_type} · {p.unit_count} units/rooms</small></div><div className="listing-content"><div className="listing-rent">{money(p.monthly_rent)} <small>/ month</small></div><h3>{p.title}</h3><p>{p.address}</p><p className="listing-desc">{p.description || 'A rental listing managed through PropManager.'}</p><button disabled={busy || applications.some((a) => a.property_id === p.id)} className="button button-dark" onClick={() => act(() => request('/api/applications', { method: 'POST', body: JSON.stringify({ property_id: p.id }) }), 'Application sent to the owner through PropManager.')}>{applications.some((a) => a.property_id === p.id) ? 'Applied' : 'Apply through broker →'}</button></div></article>) : <Empty text="No properties are listed yet." />}</div>
    </section>
    <div className="dashboard-columns"><section className="dash-section"><SectionTitle title="My applications" />{applications.length ? <div className="list-table">{applications.map((a) => <div className="data-row" key={a.id}><div><strong>{a.property_title}</strong><small>{money(a.monthly_rent)} / month · {date(a.created_at)}</small></div><Badge value={a.status} /></div>)}</div> : <Empty text="Your applications will show up here." />}</section>
      <section className="dash-section"><SectionTitle title="Report an issue" sub="Maintenance, personal safety, neighborhood concerns and other property issues." />{occupied.length ? <form className="compact-form" onSubmit={(e) => { e.preventDefault(); const form = e.currentTarget; const d = new FormData(form); act(async () => { await request('/api/tickets', { method: 'POST', body: JSON.stringify(Object.fromEntries(d)) }); form.reset(); }, 'Issue submitted to the broker.'); }}><label className="form-field">Rental or building<select name="property_id" required>{occupied.map((a) => <option value={a.property_id} key={a.property_id}>{a.property_title}</option>)}</select></label><label className="form-field">Issue title<input name="title" required minLength="3" maxLength="100" /></label><div className="form-pair"><label className="form-field">Issue type<select name="category">{['Maintenance','Plumbing','Electrical','Appliance','Structural','Personal safety','Neighbourhood safety','Security/access','Cleanliness/facilities','Other'].map((x) => <option key={x}>{x}</option>)}</select></label><label className="form-field">Priority<select name="priority">{['Low','Medium','High','Urgent'].map((x) => <option key={x}>{x}</option>)}</select></label></div><label className="form-field">Describe the issue<textarea name="description" required minLength="5" maxLength="1000" rows="3" /></label><button disabled={busy} className="button button-dark">Submit issue →</button></form> : <Empty text="After an owner accepts your application, you can report an issue for that property here." />}</section></div>
    {tickets.length > 0 && <section className="dash-section"><SectionTitle title="My maintenance history" />{tickets.map((t) => <TicketRow ticket={t} key={t.id} />)}</section>}
  </>;
}

function Owner({ properties, applications, tickets, request, act, busy }) {
  return <>
    <Stats items={[["My listings", properties.length], ["Applications", applications.length], ["Open maintenance", tickets.filter((t) => !['Resolved','Skipped'].includes(t.status)).length]]} />
    <section className="dash-section"><SectionTitle title="Add a property" sub="One owner account can manage apartments, PGs and multiple office buildings." /><form className="listing-form" onSubmit={(e) => { e.preventDefault(); const form = e.currentTarget; const d = Object.fromEntries(new FormData(form)); act(async () => { await request('/api/properties', { method: 'POST', body: JSON.stringify(d) }); form.reset(); }, 'Your property is listed.'); }}><label className="form-field">Property name<input name="title" required minLength="3" maxLength="100" placeholder="Sunrise Apartments" /></label><label className="form-field">Property type<select name="property_type">{['Apartment','PG/Hostel','Office/Commercial'].map((x) => <option key={x}>{x}</option>)}</select></label><label className="form-field">Address<input name="address" required minLength="5" maxLength="240" placeholder="Area, city" /></label><label className="form-field">Monthly rent (₹)<input name="monthly_rent" type="number" min="1" required /></label><label className="form-field">Units or rooms<input name="unit_count" type="number" min="1" max="500" defaultValue="1" /></label><label className="form-field form-wide">Description<textarea name="description" maxLength="1000" rows="2" /></label><button disabled={busy} className="button button-dark">List property →</button></form></section>
    <section className="dash-section"><SectionTitle title="My property listings" />{properties.length ? <div className="listing-grid">{properties.map((p) => <PropertyCard p={p} key={p.id} />)}</div> : <Empty text="Add your first listing above." />}</section>
    <section className="dash-section"><SectionTitle title="Renter applications" sub="Accept or decline; PropManager keeps the decision visible to the renter." />{applications.length ? applications.map((a) => <div className="data-row application-row" key={a.id}><div><strong>{a.renter_name} · {a.property_title}</strong><small>{a.renter_email} · {money(a.monthly_rent)} / month · {date(a.created_at)}</small>{a.message && <p>{a.message}</p>}</div><div className="row-actions">{a.status === 'Pending' ? <><button className="button button-dark" disabled={busy} onClick={() => act(() => request(`/api/applications/${a.id}/decision`, { method: 'POST', body: JSON.stringify({ status: 'Accepted' }) }), 'Application accepted.')}>Accept</button><button className="button button-light" disabled={busy} onClick={() => act(() => request(`/api/applications/${a.id}/decision`, { method: 'POST', body: JSON.stringify({ status: 'Declined' }) }), 'Application declined.')}>Decline</button></> : <Badge value={a.status} />}</div></div>) : <Empty text="No applications yet." />}</section>
    {tickets.length > 0 && <section className="dash-section"><SectionTitle title="Maintenance updates" sub="Requests for your properties are coordinated by the broker." />{tickets.map((t) => <TicketRow ticket={t} key={t.id} />)}</section>}
  </>;
}

function Broker({ properties, applications, pendingApps, accepted, tickets, allTickets, commissions, filter, setFilter, request, act, busy }) {
  const pendingCommission = commissions.filter((c) => c.status === 'Pending').reduce((sum, c) => sum + c.amount_paise, 0);
  return <>
    <Stats items={[["Pending applications", pendingApps.length], ["In progress", allTickets.filter((t) => t.status === 'In Progress').length], ["Pending commissions", money(pendingCommission / 100)], ["Skipped tickets", allTickets.filter((t) => t.status === 'Skipped').length]]} />
    <section className="dash-section"><SectionTitle title="Broker coordination" sub="Owners decide applications. Accepted rentals start recurring monthly charges for the renter and owner." />{applications.length ? <div className="list-table">{applications.map((a) => <div className="data-row" key={a.id}><div><strong>{a.property_title}</strong><small>{a.renter_name} → {a.owner_name} · {money(a.monthly_rent)} / month</small></div><Badge value={a.status} /></div>)}</div> : <Empty text="Applications will appear here for broker coordination." />}</section>
    <section className="dash-section"><div className="section-title-row"><SectionTitle title="Issue queue" sub="Priority and similar issues help guide broker review." /></div><div className="ticket-filters"><input aria-label="Search issues" placeholder="Search issue, renter or home" value={filter.search} onChange={(e) => setFilter({ ...filter, search: e.target.value })} /><select aria-label="Filter property" value={filter.property} onChange={(e) => setFilter({ ...filter, property: e.target.value })}><option value="All">All properties</option>{properties.map((p) => <option key={p.id} value={String(p.id)}>{p.title}</option>)}</select><select aria-label="Filter priority" value={filter.priority} onChange={(e) => setFilter({ ...filter, priority: e.target.value })}>{['All','Urgent','High','Medium','Low'].map((x) => <option key={x}>{x}</option>)}</select><select aria-label="Filter status" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>{['All','Pending','In Progress','Resolved','Skipped'].map((x) => <option key={x}>{x}</option>)}</select></div>{tickets.length ? tickets.map((t) => <BrokerTicket ticket={t} similar={allTickets.filter((other) => other.id !== t.id && other.property_id === t.property_id && other.category === t.category).length} request={request} act={act} busy={busy} key={t.id} />) : <Empty text="No issues match these filters." />}</section>
    <section className="dash-section"><SectionTitle title="Monthly commission ledger" sub="10% of monthly rent is recorded separately for each side, once per billing month. No money is collected in-app." />{commissions.length ? commissions.map((c) => <div className="data-row" key={c.id}><div><strong>{c.property_title} · {c.party === 'renter' ? c.renter_name : c.owner_name}</strong><small>{c.billing_period} · {c.party === 'renter' ? 'Renter' : 'Owner'} · 10% of {money(c.monthly_rent)} rent</small></div><b>{money(c.amount_paise / 100)}</b><select aria-label="Commission status" value={c.status} disabled={busy} onChange={(e) => act(() => request(`/api/commissions/${c.id}`, { method: 'PATCH', body: JSON.stringify({ status: e.target.value }) }), 'Monthly commission status updated.')}>{['Pending','Paid','Waived'].map((x) => <option key={x}>{x}</option>)}</select></div>) : <Empty text="Monthly charges appear here after a rental is accepted." />}</section>
  </>;
}

function BrokerTicket({ ticket, similar, request, act, busy }) {
  return <article className="broker-ticket"><TicketRow ticket={ticket} similar={similar} /><div className="ticket-manager-controls"><input aria-label="Broker note" defaultValue={ticket.manager_note} placeholder="Broker note for this ticket" maxLength="1000" id={`note-${ticket.id}`} /><select aria-label="Ticket status" value={ticket.status} disabled={busy} onChange={(e) => { const manager_note = document.getElementById(`note-${ticket.id}`).value; act(() => request(`/api/tickets/${ticket.id}`, { method: 'PATCH', body: JSON.stringify({ status: e.target.value, manager_note }) }), 'Ticket updated.'); }}>{['Pending','In Progress','Resolved','Skipped'].map((x) => <option key={x}>{x}</option>)}</select></div></article>;
}

function TicketRow({ ticket, similar = 0 }) {
  return <article className="ticket-row"><div className="ticket-row-main"><strong>{ticket.title}</strong><small>{ticket.property_title} · {ticket.renter_name} · {ticket.category}</small>{ticket.description && <p>{ticket.description}</p>}{ticket.manager_note && <p className="manager-note">Broker note: {ticket.manager_note}</p>}</div><div className="ticket-row-meta"><Badge value={ticket.priority} /><Badge value={ticket.status} />{similar > 0 && <small>{similar} similar issue{similar === 1 ? '' : 's'}</small>}<small>{date(ticket.created_at)}</small></div></article>;
}

function PropertyCard({ p }) { return <article className="listing-card"><div className="listing-art"><span>⌂</span><small>{p.property_type} · {p.unit_count} units/rooms</small></div><div className="listing-content"><div className="listing-rent">{money(p.monthly_rent)} <small>/ month</small></div><h3>{p.title}</h3><p>{p.address}</p><Badge value={p.status} /></div></article>; }
function Stats({ items }) { return <div className="stats-grid">{items.map(([title, value]) => <div className="stat-card" key={title}><small>{title}</small><strong>{value}</strong></div>)}</div>; }
function SectionTitle({ title, sub }) { return <div className="section-heading"><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div></div>; }
function Badge({ value }) { return <span className={`badge badge-${statusClass(value)}`}>{value}</span>; }
function Empty({ text }) { return <div className="empty-state">{text}</div>; }
function label(role) { return ({ renter: 'Renter', owner: 'Owner', broker: 'Broker' })[role] || 'Member'; }
function priorityRank(p) { return ({ Urgent: 4, High: 3, Medium: 2, Low: 1 })[p] || 0; }
