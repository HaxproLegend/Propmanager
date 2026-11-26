import React, { useEffect, useMemo, useState } from 'react';
import { Avatar, dateTime, label } from './ui.jsx';

const NAV = {
  renter: [
    { key: 'workspace', label: 'Overview', icon: '◫' },
    { key: 'analytics', label: 'Analytics', icon: '◔' },
    { key: 'listings', label: 'Browse homes', icon: '⌂' },
    { key: 'applications', label: 'Applications', icon: '⇄' },
    { key: 'issues', label: 'My issues', icon: '✳' },
    { key: 'ledger', label: 'Commission', icon: '₹' },
  ],
  owner: [
    { key: 'workspace', label: 'Overview', icon: '◫' },
    { key: 'analytics', label: 'Analytics', icon: '◔' },
    { key: 'listings', label: 'My listings', icon: '⌂' },
    { key: 'applications', label: 'Applications', icon: '⇄' },
    { key: 'issues', label: 'Issues', icon: '✳' },
    { key: 'ledger', label: 'Commission', icon: '₹' },
    { key: 'organizations', label: 'Organizations', icon: '▦' },
  ],
  broker: [
    { key: 'workspace', label: 'Overview', icon: '◫' },
    { key: 'analytics', label: 'Analytics', icon: '◔' },
    { key: 'listings', label: 'Properties', icon: '⌂' },
    { key: 'applications', label: 'Applications', icon: '⇄' },
    { key: 'issues', label: 'Priority queue', icon: '✳' },
    { key: 'ledger', label: 'Commission', icon: '₹' },
    { key: 'organizations', label: 'Organizations', icon: '▦' },
  ],
};

export default function AppShell({ user, request, page, setPage, onSignOut, onUpdateUser, children, refreshKey, notify }) {
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const [bellOpen, setBellOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const items = NAV[user.role] || NAV.renter;
  const isDemo = user.email.endsWith('@propmanager.demo');

  const loadNotifications = async () => {
    try {
      const data = await request('/api/notifications?limit=12');
      setNotifications(data.notifications);
      setUnread(data.unread);
    } catch { /* notifications are non-critical to the workspace */ }
  };
  useEffect(() => { loadNotifications(); }, [refreshKey]);

  const markRead = async (id) => {
    try {
      await request(`/api/notifications/${id}/read`, { method: 'PATCH', body: '{}' });
      await loadNotifications();
    } catch (err) { notify(err.message, 'error'); }
  };
  const markAll = async () => {
    try {
      await request('/api/notifications/read-all', { method: 'POST', body: '{}' });
      await loadNotifications();
      setBellOpen(false);
      notify('Notifications marked as read.');
    } catch (err) { notify(err.message, 'error'); }
  };

  const go = (key) => { setPage(key); setMobileOpen(false); setBellOpen(false); setUserOpen(false); setSearch(''); };
  const matches = useMemo(() => search.trim()
    ? [...items, { key: 'profile', label: 'Your profile', icon: '☺' }].filter((item) => item.label.toLowerCase().includes(search.toLowerCase()))
    : [], [search, items]);
  const current = [...items, { key: 'profile', label: 'Your profile' }].find((item) => item.key === page) || items[0];

  return <div className="app-shell">
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <button className="wordmark side-wordmark" onClick={() => go('workspace')}><span className="mark">P</span> propmanager</button>
      {isDemo && <div className="demo-badge"><span>DEMO DATA</span><small>Sample accounts and issues</small></div>}
      <div className="side-eyebrow">{label(user.role).toUpperCase()} WORKSPACE</div>
      <nav className="side-nav" aria-label="Workspace navigation">
        {items.map((item) => <button key={item.key} className={page === item.key ? 'active' : ''} onClick={() => go(item.key)}><span className="nav-icon">{item.icon}</span>{item.label}{item.key === 'issues' && unread > 0 && <span className="nav-dot" />}</button>)}
      </nav>
      <div className="side-foot">
        <button className={page === 'profile' ? 'active' : ''} onClick={() => go('profile')}><span className="nav-icon">☺</span>Your profile</button>
        <button onClick={onSignOut}><span className="nav-icon">↗</span>Sign out</button>
      </div>
    </aside>

    <div className="shell-main">
      <header className="topbar">
        <button className="icon-button mobile-toggle" aria-label="Toggle navigation" onClick={() => setMobileOpen(!mobileOpen)}>☰</button>
        <div className="breadcrumb"><span>Workspace</span><b>/</b><strong>{current.label}</strong></div>
        <div className="topbar-search">
          <input aria-label="Quick navigation" placeholder="Search workspace…" value={search} onChange={(event) => setSearch(event.target.value)} />
          {matches.length > 0 && <div className="search-results">{matches.map((item) => <button key={item.key} onClick={() => go(item.key)}>{item.label}</button>)}</div>}
        </div>
        <div className="topbar-actions">
          <div className="popover-anchor">
            <button className="icon-button bell" aria-label={`Notifications, ${unread} unread`} onClick={() => { setBellOpen(!bellOpen); setUserOpen(false); }}>♢{unread > 0 && <span className="count">{unread}</span>}</button>
            {bellOpen && <div className="popover notification-popover">
              <div className="popover-head"><strong>Notifications</strong><button className="text-button" onClick={markAll}>Mark all read</button></div>
              {notifications.length ? notifications.map((note) => <button key={note.id} className={`notification-row ${note.is_read ? '' : 'unread'}`} onClick={() => markRead(note.id)}><span><strong>{note.title}</strong><small>{note.body}</small><small>{dateTime(note.created_at)}</small></span></button>) : <div className="empty-state">You're all caught up.</div>}
            </div>}
          </div>
          <div className="popover-anchor">
            <button className="user-chip" onClick={() => { setUserOpen(!userOpen); setBellOpen(false); }}><Avatar name={user.name} role={user.role} /><span>{user.name}</span></button>
            {userOpen && <div className="popover user-popover"><div><strong>{user.name}</strong><small>{user.email}</small><small>{label(user.role)}</small></div><button onClick={() => go('profile')}>Your profile</button><button onClick={onSignOut}>Sign out</button></div>}
          </div>
        </div>
      </header>
      {mobileOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <main className="shell-content">{children}</main>
    </div>
    <nav className="mobile-nav" aria-label="Mobile navigation">{items.slice(0, 4).map((item) => <button key={item.key} className={page === item.key ? 'active' : ''} onClick={() => go(item.key)}><span>{item.icon}</span><small>{item.label.split(' ')[0]}</small></button>)}</nav>
  </div>;
}
