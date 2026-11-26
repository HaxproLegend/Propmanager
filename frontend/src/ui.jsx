import React, { useState } from 'react';

export const money = (value) => `₹${Number(value || 0).toLocaleString('en-IN')}`;
export const date = (seconds) => seconds ? new Date(seconds * 1000).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : '—';
export const dateTime = (seconds) => seconds ? new Date(seconds * 1000).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '—';
export const statusClass = (value) => String(value || '').toLowerCase().replaceAll(' ', '-');
export const label = (role) => ({ renter: 'Renter', owner: 'Owner', broker: 'Broker / Manager' })[role] || 'Member';
export const priorityRank = (p) => ({ Urgent: 4, High: 3, Medium: 2, Low: 1 })[p] || 0;

export function Badge({ value }) {
  return <span className={`badge badge-${statusClass(value)}`}>{value}</span>;
}

export function Stats({ items }) {
  return <div className="stats-grid">{items.map(([title, value]) => (
    <div className="stat-card" key={title}><small>{title}</small><strong>{value}</strong></div>
  ))}</div>;
}

export function SectionTitle({ title, sub, action }) {
  return <div className="section-heading"><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>{action}</div>;
}

export function Empty({ text }) {
  return <div className="empty-state">{text}</div>;
}

export function Skeleton({ count = 3 }) {
  return <div className="skeleton-stack" aria-label="Loading">{Array.from({ length: count }, (_, index) => <div className="skeleton" key={index} />)}</div>;
}

export function Avatar({ name, role }) {
  return <div className="avatar" title={label(role)}>{String(name || 'P').trim().charAt(0).toUpperCase()}</div>;
}

export function ListingImage({ src, alt, className = '', children }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <div className={`listing-art ${className}`}><span>⌂</span><small>{children}</small></div>;
  return <img className={`listing-image ${className}`} src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />;
}

export function Drawer({ open, onClose, title, sub, children, wide = false }) {
  if (!open) return null;
  return <div className="drawer-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className={`drawer ${wide ? 'drawer-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
      <div className="drawer-head"><div><div className="eyebrow">PROPMANAGER</div><h2>{title}</h2>{sub && <p>{sub}</p>}</div><button className="icon-button" aria-label="Close" onClick={onClose}>×</button></div>
      <div className="drawer-body">{children}</div>
    </aside>
  </div>;
}

export function Timeline({ events, describe, empty = 'No updates yet.' }) {
  if (!events?.length) return <Empty text={empty} />;
  return <ol className="timeline">{events.map((event) => (
    <li key={event.id} className="timeline-item">
      <span className="timeline-dot" aria-hidden="true" />
      <div><strong>{describe ? describe(event) : event.event_type}</strong>{event.note && <p>{event.note}</p>}<small>{dateTime(event.created_at)}{event.actor_name ? ` · ${event.actor_name}` : ''}</small></div>
    </li>
  ))}</ol>;
}

export function ToastStack({ toasts, onDismiss }) {
  if (!toasts?.length) return null;
  return <div className="toast-stack" aria-live="polite">{toasts.map((toast) => (
    <div className={`toast ${toast.kind || 'success'}`} key={toast.id} role="status">
      <span>{toast.message}</span><button aria-label="Dismiss" onClick={() => onDismiss(toast.id)}>×</button>
    </div>
  ))}</div>;
}

export function Tabs({ tabs, active, onChange }) {
  return <div className="tabs" role="tablist">{tabs.map((tab) => (
    <button key={tab.key} role="tab" aria-selected={active === tab.key} className={active === tab.key ? 'active' : ''} onClick={() => onChange(tab.key)}>{tab.label}</button>
  ))}</div>;
}

export function ApplicationEventLabel(event) {
  const map = { submitted: 'Application submitted', decision: `Decision: ${event.new_status}`, rental_ended: 'Rental ended' };
  return map[event.event_type] || event.event_type;
}
