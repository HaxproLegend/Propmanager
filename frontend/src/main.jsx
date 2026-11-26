import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import AppShell from './AppShell.jsx';
import Dashboard from './Dashboard.jsx';
import Policy from './Policy.jsx';
import { ToastStack } from './ui.jsx';
import './styles.css';

const api = async (path, options = {}) => {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (options.method && options.method !== 'GET') {
    if (!getCookie('pm_csrf')) await fetch('/api/auth/csrf', { credentials: 'same-origin' });
    headers['X-CSRF-Token'] = getCookie('pm_csrf');
  }
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
};

function getCookie(name) {
  return document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))?.slice(name.length + 1) || '';
}

function App() {
  const [user, setUser] = useState(null);
  const [mode, setMode] = useState('home');
  const [authRole, setAuthRole] = useState('renter');
  const [page, setPage] = useState('workspace');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [toasts, setToasts] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    api('/api/auth/csrf').catch(() => {});
    api('/api/auth/me').then(({ user: account }) => setUser(account)).catch(() => {});
  }, []);

  const notify = (message, kind = 'success') => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((current) => [...current, { id, message, kind }]);
    setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4500);
  };
  const dismiss = (id) => setToasts((current) => current.filter((toast) => toast.id !== id));

  const go = (next) => { setError(''); setMode(next); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true); setError('');
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api(mode === 'register' ? '/api/auth/register' : '/api/auth/login', { method: 'POST', body: JSON.stringify(values) });
      setUser(result.user); setPage('workspace'); setMode('home');
      notify(`Welcome, ${result.user.name.split(' ')[0]}.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const demoLogin = async (email) => {
    setBusy(true); setError('');
    try {
      const result = await api('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password: 'DemoPass123!' }) });
      setUser(result.user); setPage('workspace'); setMode('home');
      notify(`Signed in as ${result.user.name.split(' ')[0]}.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const chooseAuthRole = (role) => {
    setAuthRole(role);
    if (role === 'broker' && mode === 'register') setMode('login');
  };
  const signOut = async () => {
    try { await api('/api/auth/logout', { method: 'POST', body: '{}' }); } catch { /* sign out locally regardless */ }
    setUser(null); setPage('workspace'); go('home');
  };

  return <>
    {user ? <AppShell user={user} request={api} page={page} setPage={setPage} onSignOut={signOut} onUpdateUser={setUser} refreshKey={refreshKey} notify={notify}>
      <Dashboard user={user} request={api} page={page} setPage={setPage} notify={notify} onChanged={() => setRefreshKey((key) => key + 1)} onUpdateUser={setUser} />
    </AppShell> : <>
      <header className="header">
        <a className="wordmark" href="#home" onClick={(event) => { event.preventDefault(); go('home'); }}><span className="mark">P</span> propmanager</a>
        <nav aria-label="Main navigation" className="header-nav"><a href="#how-it-works" onClick={() => go('home')}>How it works</a><a href="#for-renters" onClick={() => go('home')}>For renters</a><a href="#for-owners" onClick={() => go('home')}>For owners</a></nav>
        <div className="header-actions"><button className="button button-light" onClick={() => go('login')}>Sign in</button><button className="button button-dark" onClick={() => go('register')}>Get started <span aria-hidden="true">↗</span></button></div>
      </header>
      {mode === 'login' || mode === 'register' ? <main className="auth-layout">
        <section className="auth-story"><div className="eyebrow">A BETTER WAY TO RENT</div><h1>{mode === 'login' ? 'Good to have you back.' : 'Start with a clearer rental experience.'}</h1><p>One trusted place for renters, owners and the brokers who bring them together.</p><div className="story-note"><span className="story-icon">✳</span><span>Find your place. Keep the important details moving.</span></div></section>
        <section className="auth-panel">
          <button className="back-link" onClick={() => go('home')}>← Back to PropManager</button>
          <h2>{mode === 'login' ? 'Sign in' : 'Create your account'}</h2>
          <p className="auth-subtitle">{mode === 'login' ? 'Enter your details to continue.' : 'Join as a renter or property owner.'}</p>
          <div className="auth-quick" role="group" aria-label="Choose your role">
            {[['renter', 'Renter', '⌂'], ['owner', 'Owner', '▤'], ['broker', 'Broker', '✳']].map(([key, quickLabel, icon]) => (
              <button key={key} className={authRole === key ? 'active' : ''} onClick={() => chooseAuthRole(key)}>
                <span>{icon}</span><strong>{quickLabel}</strong><small>{key === 'broker' ? 'Provisioned' : 'Quick access'}</small>
              </button>
            ))}
          </div>
          {authRole === 'broker' && <p className="auth-note">Broker accounts are created by the project operator. Use a demo sign-in below or contact your administrator.</p>}
          {error && <div role="alert" className="form-error">{error}</div>}
          <form onSubmit={submit}>
            {mode === 'register' && <label className="form-field">Full name<input name="name" autoComplete="name" required minLength="2" maxLength="80" placeholder="Your name" /></label>}
            <label className="form-field">Email address<input name="email" type="email" autoComplete="email" required maxLength="254" placeholder="you@example.com" /></label>
            <label className="form-field">Password<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'login' ? undefined : 12} maxLength="128" placeholder={mode === 'register' ? 'At least 12 characters' : 'Your password'} /></label>
            {mode === 'register' && authRole !== 'broker' && <label className="form-field">I’m joining as<select name="role" value={authRole} onChange={(event) => setAuthRole(event.target.value)}><option value="renter">Renter</option><option value="owner">Property owner</option></select></label>}
            {mode === 'register' && authRole === 'broker' && <input type="hidden" name="role" value="renter" />}
            <button className="button button-dark submit-button" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'} <span aria-hidden="true">→</span></button>
          </form>
          {mode === 'login' && <div className="demo-logins"><small>Quick demo sign-in (after <code>seed-demo</code>)</small><div><button onClick={() => demoLogin('renter-a@propmanager.demo')}>Renter</button><button onClick={() => demoLogin('owner@propmanager.demo')}>Owner</button><button onClick={() => demoLogin('broker@propmanager.demo')}>Broker</button></div></div>}
          <p className="switch-mode">{mode === 'login' ? 'New to PropManager?' : 'Already have an account?'} <button onClick={() => go(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button></p>
          <button className="policy-link" onClick={() => go('policy')}>How we handle issues & applications →</button>
        </section>
      </main> : mode === 'policy' ? <main className="policy-page"><button className="back-link" onClick={() => go('home')}>← Back to PropManager</button><Policy /></main> : <Landing onAction={go} />}
      <footer className="footer"><a className="wordmark" href="#home" onClick={(event) => { event.preventDefault(); go('home'); }}><span className="mark">P</span> propmanager</a><span>Renting, with a little more clarity.</span><button className="footer-link" onClick={() => go('policy')}>How we handle issues & applications</button><span>© 2026 PropManager</span></footer>
    </>}
    <ToastStack toasts={toasts} onDismiss={dismiss} />
  </>;
}

function Landing({ onAction }) {
  return <main>
    <section className="hero">
      <div className="hero-copy"><div className="eyebrow"><span className="eyebrow-dot" /> RENTAL MANAGEMENT, MADE HUMAN</div><h1>Renting should feel <em>straightforward.</em></h1><p className="hero-lead">A clearer connection between the people who rent, the people who own, and the local experts in between.</p><div className="hero-buttons"><button className="button button-dark button-large" onClick={() => onAction('register')}>Get started <span aria-hidden="true">↗</span></button><span className="hero-hint">Sign in from the top right</span></div><div className="hero-caption"><span className="avatar-stack"><i>R</i><i>O</i><i>B</i></span><span>For renters, owners and brokers</span></div></div>
      <div className="hero-art" aria-label="Illustration of a welcoming rental home"><div className="sun-disc" /><div className="art-label label-left"><span className="label-icon">⌂</span><span>Find a place<br /><b>that feels right</b></span></div><div className="house"><div className="roof" /><div className="house-front"><div className="upper-window"><i /><i /></div><div className="door" /><div className="lower-window"><i /><i /></div></div><div className="plant plant-one"><i /><i /><b /></div><div className="plant plant-two"><i /><i /><b /></div></div><div className="art-label label-right"><span className="label-icon">↗</span><span>One helpful<br /><b>step at a time</b></span></div><div className="art-ground" /></div>
      <div className="hero-bottom"><span>THOUGHTFUL RENTALS. BETTER CONNECTIONS.</span><span className="scroll-cue">SCROLL TO EXPLORE ↓</span></div>
    </section>
    <section className="intro-section" id="how-it-works"><div className="section-kicker">A MORE CONNECTED RENTAL JOURNEY</div><div className="intro-grid"><h2>Less chasing.<br /><em>More moving forward.</em></h2><p>PropManager brings rental conversations and practical support into one place. A local broker helps coordinate the details, so renters and owners know what happens next.</p></div></section>
    <section className="roles-section"><div className="role-card" id="for-renters"><div className="role-index">01 / RENTERS</div><h3>Find your next place.</h3><p>Explore homes, send an application and keep track of the support you need.</p><button className="text-button" onClick={() => onAction('register')}>Join as a renter →</button></div><div className="role-card owner-card" id="for-owners"><div className="role-index">02 / OWNERS</div><h3>Feel in the loop.</h3><p>Connect with renters and let a broker help coordinate the day-to-day.</p><button className="text-button" onClick={() => onAction('register')}>Join as an owner →</button></div><div className="role-card broker-card"><div className="role-index">03 / BROKERS</div><h3>Keep things moving.</h3><p>Coordinate communication, applications and maintenance requests. Broker accounts are provisioned by the operator.</p><span className="role-note">Provisioned by your brokerage</span></div></section>
    <section className="proof-section"><div className="section-kicker">WHY PROPMANAGER</div><div className="proof-head"><h2>Built for the three sides of every rental.</h2><p>One workspace instead of scattered chats and spreadsheets — with role-aware access, visible histories and a ledger that records obligations without collecting money.</p></div>
      <div className="proof-grid"><div><strong>3</strong><span>roles in one app</span></div><div><strong>8</strong><span>seeded demo listings</span></div><div><strong>4</strong><span>issue states with history</span></div><div><strong>0</strong><span>payments collected in-app</span></div></div>
    </section>

    <section className="compare-section"><div className="section-kicker">A FAIRER WORKFLOW</div><h2>How we compare</h2><p>We are not trying to replace the conversation. We make the important parts visible to everyone involved.</p>
      <table className="compare-table"><thead><tr><th>What matters</th><th>Spreadsheets</th><th>Group chats</th><th>PropManager</th></tr></thead><tbody>
        <tr><td>Role-based access</td><td>—</td><td>Partly</td><td>✓</td></tr>
        <tr><td>Unit and room inventory</td><td>—</td><td>—</td><td>✓</td></tr>
        <tr><td>Visible application &amp; issue history</td><td>—</td><td>Partly</td><td>✓</td></tr>
        <tr><td>Recurring commission ledger</td><td>—</td><td>—</td><td>✓</td></tr>
        <tr><td>No automatic rejection or scoring</td><td>—</td><td>—</td><td>✓</td></tr>
        <tr><td>Portfolio analytics</td><td>Manual</td><td>—</td><td>✓</td></tr>
      </tbody></table>
    </section>

    <section className="signal-section"><div><div className="section-kicker">A SNAPSHOT, NOT A PITCH</div><h2>Numbers from a working demo</h2><p>Illustrative figures from the seeded sample data — not claims about live customers.</p></div>
      <div className="signal-bars">{[['Applications tracked', 7, 100], ['Issues in queue', 9, 90], ['Resolved with a reason', 2, 25], ['Commission entries', 10, 80]].map(([label, value, width]) => <div className="signal-row" key={label}><span>{label}</span><div><i style={{ width: `${width}%` }} /></div><strong>{value}</strong></div>)}</div>
    </section>

    <section className="closing-cta"><div><div className="section-kicker">YOUR NEXT CHAPTER STARTS HERE</div><h2>A clearer way to find your place.</h2></div><button className="button button-dark button-large" onClick={() => onAction('register')}>Create your account ↗</button></section>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
