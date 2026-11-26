import React, { useMemo, useState } from 'react';
import { Badge, Empty, SectionTitle, Tabs, date, money, priorityRank } from './ui.jsx';

const STATUSES = ['Pending', 'In Progress', 'Resolved', 'Skipped'];
const PRIORITIES = ['Urgent', 'High', 'Medium', 'Low'];

export default function BrokerQueue({ tickets, properties, request, act, busy, notify }) {
  const [view, setView] = useState('priority');
  const [filter, setFilter] = useState({ status: 'All', priority: 'All', property: 'All', search: '' });
  const [selected, setSelected] = useState([]);
  const [bulkStatus, setBulkStatus] = useState('In Progress');

  const filtered = useMemo(() => tickets.filter((ticket) =>
    (filter.status === 'All' || ticket.status === filter.status) &&
    (filter.priority === 'All' || ticket.priority === filter.priority) &&
    (filter.property === 'All' || String(ticket.property_id) === filter.property) &&
    `${ticket.title} ${ticket.property_title} ${ticket.renter_name} ${ticket.category}`.toLowerCase().includes(filter.search.toLowerCase())
  ), [tickets, filter]);

  const ranked = useMemo(() => [...filtered].sort((a, b) =>
    (priorityRank(b.priority) - priorityRank(a.priority)) ||
    ((b.similar_resident_count || 0) - (a.similar_resident_count || 0)) ||
    (a.created_at - b.created_at)
  ), [filtered]);

  const changeStatus = (ticket, status, note) => {
    if (status === 'Skipped' && !String(note || '').trim()) {
      notify('Add a reason before skipping an issue.', 'error');
      return;
    }
    act(() => request(`/api/tickets/${ticket.id}`, { method: 'PATCH', body: JSON.stringify({ status, manager_note: note || ticket.manager_note || '' }) }), `Issue moved to ${status}.`);
  };

  const runBulk = async () => {
    if (!selected.length) return;
    if (bulkStatus === 'Skipped') { notify('Add a reason to each issue before skipping it.', 'error'); return; }
    await act(() => Promise.all(selected.map((id) => request(`/api/tickets/${id}`, {
      method: 'PATCH', body: JSON.stringify({ status: bulkStatus, manager_note: 'Bulk status update' }),
    }))), `${selected.length} issues moved to ${bulkStatus}.`);
    setSelected([]);
  };

  const savedViews = [
    { label: 'Urgent open', apply: () => setFilter({ status: 'Pending', priority: 'Urgent', property: 'All', search: '' }) },
    { label: 'Oldest open', apply: () => setFilter({ status: 'All', priority: 'All', property: 'All', search: '', sort: 'oldest' }) },
    { label: 'All issues', apply: () => setFilter({ status: 'All', priority: 'All', property: 'All', search: '' }) },
  ];

  const controls = <div className="queue-controls">
    <input aria-label="Search issues" placeholder="Search issue, renter or home" value={filter.search} onChange={(e) => setFilter({ ...filter, search: e.target.value })} />
    <select aria-label="Filter property" value={filter.property} onChange={(e) => setFilter({ ...filter, property: e.target.value })}><option value="All">All properties</option>{properties.map((p) => <option key={p.id} value={String(p.id)}>{p.title}</option>)}</select>
    <select aria-label="Filter priority" value={filter.priority} onChange={(e) => setFilter({ ...filter, priority: e.target.value })}><option value="All">All priorities</option>{PRIORITIES.map((p) => <option key={p}>{p}</option>)}</select>
    <select aria-label="Filter status" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}><option value="All">All statuses</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select>
  </div>;

  return <section className="dash-section">
    <SectionTitle title="Priority queue" sub="Importance, elapsed time and similar reports guide a human decision. No automatic scoring." action={<Tabs tabs={[{ key: 'priority', label: 'Priority list' }, { key: 'board', label: 'Board' }]} active={view} onChange={setView} />} />
    <div className="saved-views">{savedViews.map((saved) => <button className="chip" key={saved.label} onClick={saved.apply}>{saved.label}</button>)}</div>
    {controls}
    {selected.length > 0 && <div className="bulk-bar"><span>{selected.length} selected</span><select aria-label="Bulk status" value={bulkStatus} onChange={(e) => setBulkStatus(e.target.value)}>{STATUSES.filter((s) => s !== 'Skipped').map((s) => <option key={s}>{s}</option>)}</select><button className="button button-dark" disabled={busy} onClick={runBulk}>Apply</button></div>}
    {ranked.length === 0 ? <Empty text="No issues match these filters." /> : view === 'board' ? <div className="queue-board">{STATUSES.map((status) => <div className="board-column" key={status}><div className="board-column-head"><strong>{status}</strong><span>{ranked.filter((t) => t.status === status).length}</span></div>{ranked.filter((t) => t.status === status).map((ticket) => <BoardCard key={ticket.id} ticket={ticket} changeStatus={changeStatus} busy={busy} />)}</div>)}</div> :
      <div className="priority-list">{ranked.map((ticket, index) => <PriorityRow key={ticket.id} ticket={ticket} rank={index + 1} selected={selected.includes(ticket.id)} onSelect={() => setSelected(selected.includes(ticket.id) ? selected.filter((id) => id !== ticket.id) : [...selected, ticket.id])} changeStatus={changeStatus} busy={busy} />)}</div>}
  </section>;
}

function Factors({ ticket }) {
  return <div className="factor-list"><span>{ticket.age_hours ?? 0}h open</span>{(ticket.similar_issue_count ?? 0) > 0 && <span>{ticket.similar_issue_count} similar report{ticket.similar_issue_count === 1 ? '' : 's'}</span>}{(ticket.similar_resident_count ?? 0) > 0 && <span>{ticket.similar_resident_count} resident{ticket.similar_resident_count === 1 ? '' : 's'}</span>}<span>{date(ticket.created_at)}</span></div>;
}

function PriorityRow({ ticket, rank, selected, onSelect, changeStatus, busy }) {
  const [note, setNote] = useState(ticket.manager_note || '');
  return <article className="priority-row">
    <div className="priority-rank">{rank}</div>
    <label className="check"><input type="checkbox" checked={selected} onChange={onSelect} aria-label={`Select ${ticket.title}`} /></label>
    <div className="priority-main"><strong>{ticket.title}</strong><small>{ticket.property_title} · {ticket.renter_name} · {ticket.category}</small><p>{ticket.description}</p><Factors ticket={ticket} />{ticket.manager_note && <p className="manager-note">Broker note: {ticket.manager_note}</p>}</div>
    <div className="priority-controls"><Badge value={ticket.priority} /><Badge value={ticket.status} /><input aria-label="Broker note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason required when skipping" maxLength="1000" /><select aria-label="Ticket status" value={ticket.status} disabled={busy} onChange={(e) => changeStatus(ticket, e.target.value, note)}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></div>
  </article>;
}

function BoardCard({ ticket, changeStatus, busy }) {
  const [note, setNote] = useState(ticket.manager_note || '');
  return <article className="board-card"><strong>{ticket.title}</strong><small>{ticket.property_title}</small><div className="board-tags"><Badge value={ticket.priority} /><Badge value={ticket.category} /></div><Factors ticket={ticket} /><input aria-label="Broker note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Broker note" /><select aria-label="Ticket status" value={ticket.status} disabled={busy} onChange={(e) => changeStatus(ticket, e.target.value, note)}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></article>;
}
