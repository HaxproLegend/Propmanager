import React, { useCallback, useEffect, useState } from 'react';
import { Badge, Empty, SectionTitle, Skeleton, date, dateTime, money } from './ui.jsx';

const ORG_ROLES = ['org_admin', 'manager', 'broker', 'accountant', 'technician'];
const LEAD_STATUS = ['New', 'Contacted', 'Qualified', 'Converted', 'Lost'];

export default function Organizations({ user, request, act, busy, notify, properties }) {
  const [orgs, setOrgs] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newOrg, setNewOrg] = useState({ name: '', slug: '' });
  const [invite, setInvite] = useState({ email: '', role: 'manager' });
  const [term, setTerm] = useState({ party: 'owner', rate_basis_points: 1000, effective_from: '' });
  const [lead, setLead] = useState({ name: '', email: '', phone: '', source: 'Manual', notes: '' });
  const [assignId, setAssignId] = useState('');
  const [settings, setSettings] = useState({ overdue_hours: 48, escalation_hours: 72 });
  const [vendor, setVendor] = useState({ name: '', service_type: 'General', phone: '', email: '' });

  const loadOrgs = useCallback(async () => {
    setLoading(true);
    try {
      const result = await request('/api/orgs');
      setOrgs(result.organizations);
      if (!selectedId && result.organizations.length) setSelectedId(result.organizations[0].id);
    } catch (err) { notify(err.message, 'error'); }
    finally { setLoading(false); }
  }, [request, notify, selectedId]);

  const loadDetail = useCallback(async () => {
    if (!selectedId) { setData(null); return; }
    try {
      const [detail, summary, members, invitations, terms, leads, settings, vendors, audit] = await Promise.all([
        request(`/api/orgs/${selectedId}`),
        request(`/api/orgs/${selectedId}/dashboard`),
        request(`/api/orgs/${selectedId}/members`),
        request(`/api/orgs/${selectedId}/invitations`),
        request(`/api/orgs/${selectedId}/commission-terms`),
        request(`/api/orgs/${selectedId}/leads`),
        request(`/api/orgs/${selectedId}/settings`),
        request(`/api/orgs/${selectedId}/vendors`),
        request(`/api/orgs/${selectedId}/audit`),
      ]);
      setData({ detail: detail.organization, summary: summary.summary, members: members.members,
                invitations: invitations.invitations, terms: terms.terms, leads: leads.leads,
                settings: settings.settings, vendors: vendors.vendors, audit: audit.events });
      setSettings(settings.settings);
    } catch (err) { notify(err.message, 'error'); }
  }, [selectedId, request, notify]);

  useEffect(() => { loadOrgs(); }, [loadOrgs]);
  useEffect(() => { loadDetail(); }, [loadDetail]);

  const refresh = async () => { await loadDetail(); await loadOrgs(); };
  const mutate = async (operation, message) => {
    try { await operation(); await refresh(); notify(message); }
    catch (err) { notify(err.message, 'error'); }
  };
  const canManage = user.role === 'broker' || data?.detail?.member_role === 'org_admin';

  if (loading) return <Skeleton count={3} />;

  return <div>
    <div className="page-head"><div className="eyebrow">B2B OPERATIONS · ORGANIZATIONS</div><h1>Portfolio workspace</h1><p>Manage brokerage teams, linked properties, commission terms and owner leads.</p></div>

    <section className="dash-section"><SectionTitle title="Your organizations" sub={orgs.length ? 'Select a portfolio to open its operations view.' : 'Create an organization to start a shared brokerage workspace.'} />
      {orgs.length ? <div className="org-pills">{orgs.map((org) => <button key={org.id} className={selectedId === org.id ? 'active' : ''} onClick={() => setSelectedId(org.id)}><strong>{org.name}</strong><small>{org.member_role || 'member'}</small></button>)}</div> : <Empty text="No organizations yet." />}
      <form className="inline-form" onSubmit={(event) => { event.preventDefault(); mutate(() => request('/api/orgs', { method: 'POST', body: JSON.stringify(newOrg) }), 'Organization created.'); setNewOrg({ name: '', slug: '' }); }}>
        <input aria-label="Organization name" required minLength="3" maxLength="80" placeholder="New organization name" value={newOrg.name} onChange={(e) => setNewOrg({ ...newOrg, name: e.target.value })} />
        <input aria-label="Organization slug" placeholder="slug (optional)" value={newOrg.slug} onChange={(e) => setNewOrg({ ...newOrg, slug: e.target.value })} />
        <button className="button button-dark" disabled={busy}>Create organization</button>
      </form>
    </section>

    {!data ? <Empty text="Select an organization to see its portfolio." /> : <>
      <section className="dash-section"><SectionTitle title={`${data.detail.name} · portfolio health`} sub="Live rollup across linked properties, units, applications and issues." />
        <div className="stats-grid">
          {[['Properties', data.summary.properties], ['Units', data.summary.units], ['Occupied units', data.summary.occupied_units], ['Occupancy', `${data.summary.occupancy_percent}%`], ['Active rentals', data.summary.active_rentals], ['Pending applications', data.summary.pending_applications], ['Open issues', data.summary.open_issues], ['Pending commission', money(data.summary.pending_commission_paise / 100)]].map(([title, value]) => <div className="stat-card" key={title}><small>{title}</small><strong>{value}</strong></div>)}
        </div>
        <div className="occupancy-bar"><div style={{ width: `${data.summary.occupancy_percent}%` }} /></div>
        <div className="export-row"><span>Export</span>{['commissions', 'properties', 'issues', 'leads'].map((type) => <a className="button button-light" key={type} href={`/api/orgs/${selectedId}/export.csv?type=${type}`} download>{type} CSV ↓</a>)}</div>
      </section>

      <div className="dashboard-columns">
        <section className="dash-section"><SectionTitle title="Team members" sub={`Your role: ${data.detail.member_role || 'member'}`} />
          {data.members.length ? <div className="list-table">{data.members.map((member) => <div className="data-row" key={member.id}><div><strong>{member.name}</strong><small>{member.email}</small></div>{canManage ? <select aria-label="Organization role" value={member.role} onChange={(e) => mutate(() => request(`/api/orgs/${selectedId}/members/${member.user_id}`, { method: 'PATCH', body: JSON.stringify({ role: e.target.value }) }), 'Role updated.')}>{ORG_ROLES.map((role) => <option key={role}>{role}</option>)}</select> : <Badge value={member.role} />}</div>)}</div> : <Empty text="No team members yet." />}
          {canManage && <form className="inline-form" onSubmit={(event) => { event.preventDefault(); mutate(() => request(`/api/orgs/${selectedId}/invitations`, { method: 'POST', body: JSON.stringify(invite) }), 'Invitation created. Copy the token and share it.'); setInvite({ email: '', role: 'manager' }); }}><input aria-label="Invite email" type="email" required placeholder="colleague@example.com" value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} /><select aria-label="Invite role" value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })}>{ORG_ROLES.map((role) => <option key={role}>{role}</option>)}</select><button className="button button-dark" disabled={busy}>Invite</button></form>}
          {data.invitations.length > 0 && <div className="sub-list"><small>Pending invitations</small>{data.invitations.filter((row) => !row.accepted_by).map((row) => <div className="data-row" key={row.id}><div><strong>{row.email}</strong><small>{row.role} · expires {date(row.expires_at)}</small></div></div>)}</div>}
        </section>

        <section className="dash-section"><SectionTitle title="Commission terms" sub="A property linked to this organization uses its active rate for future monthly cycles." />
          {data.terms.length ? <div className="list-table">{data.terms.map((row) => <div className="data-row" key={row.id}><div><strong>{row.party}</strong><small>from {date(row.effective_from)}</small></div><b>{(row.rate_basis_points / 100).toFixed(row.rate_basis_points % 100 ? 2 : 0)}%</b></div>)}</div> : <Empty text="No custom terms; the default 10% per side applies." />}
          {canManage && <form className="inline-form" onSubmit={(event) => { event.preventDefault(); mutate(() => request(`/api/orgs/${selectedId}/commission-terms`, { method: 'POST', body: JSON.stringify(term) }), 'Commission term saved.'); }}><select aria-label="Party" value={term.party} onChange={(e) => setTerm({ ...term, party: e.target.value })}><option value="owner">Owner</option><option value="renter">Renter</option></select><input aria-label="Rate in basis points" type="number" min="0" max="10000" required value={term.rate_basis_points} onChange={(e) => setTerm({ ...term, rate_basis_points: Number(e.target.value) })} /><input aria-label="Effective date" type="date" value={term.effective_from} onChange={(e) => setTerm({ ...term, effective_from: e.target.value })} /><button className="button button-dark" disabled={busy}>Set rate</button></form>}
        </section>
      </div>

      <section className="dash-section"><SectionTitle title="Linked properties" sub="Assign a listing to this portfolio so its units and commissions roll up here." />
        <div className="list-table">{properties.filter((property) => property.org_id === selectedId).map((property) => <div className="data-row" key={property.id}><div><strong>{property.title}</strong><small>{property.address} · {property.unit_count} units</small></div><button className="button button-light" disabled={busy || !canManage} onClick={() => mutate(() => request(`/api/orgs/${selectedId}/properties/${property.id}`, { method: 'DELETE' }), 'Property unlinked.')}>Unlink</button></div>)}</div>
        {canManage && <form className="inline-form" onSubmit={(event) => { event.preventDefault(); if (!assignId) return; mutate(() => request(`/api/orgs/${selectedId}/properties/${assignId}`, { method: 'POST', body: '{}' }), 'Property linked.'); setAssignId(''); }}><select aria-label="Property to link" value={assignId} onChange={(e) => setAssignId(e.target.value)}><option value="">Choose a property</option>{properties.filter((property) => property.org_id !== selectedId).map((property) => <option value={property.id} key={property.id}>{property.title}</option>)}</select><button className="button button-dark" disabled={busy}>Link property</button></form>}
      </section>

      <section className="dash-section"><SectionTitle title="Owner leads" sub="A lightweight CRM for interested owners and tenants." />
        <form className="inline-form" onSubmit={(event) => { event.preventDefault(); mutate(() => request(`/api/orgs/${selectedId}/leads`, { method: 'POST', body: JSON.stringify(lead) }), 'Lead added.'); setLead({ name: '', email: '', phone: '', source: 'Manual', notes: '' }); }}>
          <input aria-label="Lead name" required minLength="2" placeholder="Name" value={lead.name} onChange={(e) => setLead({ ...lead, name: e.target.value })} />
          <input aria-label="Lead email" type="email" required placeholder="Email" value={lead.email} onChange={(e) => setLead({ ...lead, email: e.target.value })} />
          <input aria-label="Lead phone" placeholder="Phone" value={lead.phone} onChange={(e) => setLead({ ...lead, phone: e.target.value })} />
          <select aria-label="Lead source" value={lead.source} onChange={(e) => setLead({ ...lead, source: e.target.value })}>{['Manual', 'Website', 'Referral', 'Walk-in', 'Other'].map((source) => <option key={source}>{source}</option>)}</select>
          <input aria-label="Lead notes" placeholder="Notes" value={lead.notes} onChange={(e) => setLead({ ...lead, notes: e.target.value })} />
          <button className="button button-dark" disabled={busy}>Add lead</button>
        </form>
        {data.leads.length ? <div className="list-table">{data.leads.map((row) => <div className="data-row application-row" key={row.id}><div><strong>{row.name}</strong><small>{row.email}{row.phone ? ` · ${row.phone}` : ''} · {row.source} · {date(row.created_at)}</small>{row.notes && <p>{row.notes}</p>}</div><select aria-label="Lead status" value={row.status} disabled={busy} onChange={(e) => mutate(() => request(`/api/orgs/${selectedId}/leads/${row.id}`, { method: 'PATCH', body: JSON.stringify({ status: e.target.value, notes: row.notes }) }), 'Lead updated.')}>{LEAD_STATUS.map((status) => <option key={status}>{status}</option>)}</select></div>)}</div> : <Empty text="No leads yet." />}
      </section>

      <div className="dashboard-columns">
        <section className="dash-section"><SectionTitle title="Service thresholds" sub="Advisory only — nothing changes status automatically." />
          <form className="inline-form" onSubmit={(event) => { event.preventDefault(); mutate(() => request(`/api/orgs/${selectedId}/settings`, { method: 'PATCH', body: JSON.stringify(settings) }), 'Thresholds saved.'); }}>
            <label className="form-field">Mark overdue after<input aria-label="Overdue hours" type="number" min="1" max="720" required value={settings.overdue_hours} onChange={(e) => setSettings({ ...settings, overdue_hours: Number(e.target.value) })} /><small>hours</small></label>
            <label className="form-field">Flag for escalation after<input aria-label="Escalation hours" type="number" min="1" max="2160" required value={settings.escalation_hours} onChange={(e) => setSettings({ ...settings, escalation_hours: Number(e.target.value) })} /><small>hours</small></label>
            <button className="button button-dark" disabled={busy || !canManage}>Save thresholds</button>
          </form>
        </section>

        <section className="dash-section"><SectionTitle title="Vendors and technicians" sub="Assign external help to issues without leaving PropManager." />
          {data.vendors.length ? <div className="list-table">{data.vendors.map((row) => <div className="data-row" key={row.id}><div><strong>{row.name}</strong><small>{row.service_type}{row.phone ? ` · ${row.phone}` : ''}</small></div></div>)}</div> : <Empty text="No vendors added yet." />}
          {canManage && <form className="inline-form" onSubmit={(event) => { event.preventDefault(); mutate(() => request(`/api/orgs/${selectedId}/vendors`, { method: 'POST', body: JSON.stringify(vendor) }), 'Vendor added.'); setVendor({ name: '', service_type: 'General', phone: '', email: '' }); }}>
            <input aria-label="Vendor name" required minLength="2" placeholder="Vendor name" value={vendor.name} onChange={(e) => setVendor({ ...vendor, name: e.target.value })} />
            <input aria-label="Service type" placeholder="Service" value={vendor.service_type} onChange={(e) => setVendor({ ...vendor, service_type: e.target.value })} />
            <input aria-label="Vendor phone" placeholder="Phone" value={vendor.phone} onChange={(e) => setVendor({ ...vendor, phone: e.target.value })} />
            <button className="button button-dark" disabled={busy}>Add vendor</button>
          </form>}
        </section>
      </div>

      <section className="dash-section"><SectionTitle title="Audit log" sub="Read-only record of important changes. Events cannot be edited or deleted in the app." />
        {data.audit.length ? <div className="list-table">{data.audit.map((event) => <div className="data-row" key={event.id}><div><strong>{event.action}</strong><small>{event.entity_type} #{event.entity_id} · {event.details}</small></div><small>{event.actor_name || 'System'} · {dateTime(event.created_at)}</small></div>)}</div> : <Empty text="No audited changes yet." />}
      </section>
    </>}
  </div>;
}
