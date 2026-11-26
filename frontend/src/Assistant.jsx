import React, { useEffect, useRef, useState } from 'react';

const PAGE_RULES = [
  { test: /(analytics|charts?|numbers|statistics|insights|deep dive)/i, page: 'analytics', reply: 'Opening analytics with charts and detailed tables.' },
  { test: /(urgent|priority|queue|triage)/i, page: 'issues', reply: 'Opening the priority queue. Importance, age and similar reports are shown there.' },
  { test: /(issue|ticket|maintenance|problem|repair|plumb|electric|safety|leak)/i, page: 'issues', reply: 'Opening your issues view.' },
  { test: /(appl(y|ication)|decision|accepted)/i, page: 'applications', reply: 'Opening applications. Use Timeline on any row to see its history.' },
  { test: /(commission|ledger|fee|rent due)/i, page: 'ledger', reply: 'Opening the commission ledger.' },
  { test: /(organi[sz]ation|team|portfolio|lead|invite|member)/i, page: 'organizations', reply: 'Opening the organization workspace.' },
  { test: /(profile|account|my name|settings)/i, page: 'profile', reply: 'Opening your profile.' },
  { test: /(notification|alert)/i, kind: 'notifications', reply: 'Notifications are in the bell at the top of the workspace.' },
  { test: /(browse|search|find|listing|property|flat|pg|room|office)/i, page: 'listings', reply: 'Opening listings. You can filter by location, type, rent and availability.' },
  { test: /(overview|dashboard|summary|go home|start again)/i, page: 'workspace', reply: 'Back to the overview.' },
];

const SUGGESTIONS = [
  'Browse homes',
  'My applications',
  'Priority queue',
  'Commission ledger',
  'Organizations',
  'Show analytics',
];

function parseMessage(text, context, user) {
  const query = text.trim();
  const lower = query.toLowerCase();
  if (!lower) return null;
  if (/(help|what can you do|how do i|commands)/.test(lower)) {
    return { kind: 'help', reply: 'I can open screens for you. Try “show urgent issues”, “open my applications”, “browse PG rooms”, “show the commission ledger”, or name a property, application or issue.' };
  }

  const candidates = [
    ...context.properties.map((item) => ({ kind: 'listing', id: item.id, title: item.title, label: 'listing' })),
    ...context.applications.map((item) => ({ kind: 'application', id: item.id, title: item.property_title, label: 'application' })),
    ...context.tickets.map((item) => ({ kind: 'ticket', id: item.id, title: item.title, label: 'issue' })),
  ].sort((a, b) => b.title.length - a.title.length);
  const named = candidates.find((item) => item.title && lower.includes(item.title.toLowerCase()));
  if (named) return { ...named, reply: `Opening the ${named.label} “${named.title}”.` };

  const rule = PAGE_RULES.find((item) => item.test.test(lower));
  if (rule) {
    let reply = rule.reply;
    if (rule.page === 'issues') reply = user.role === 'broker' ? 'Opening the broker priority queue.' : 'Opening your issues view.';
    return { ...rule, reply };
  }
  return { kind: 'help', reply: `I couldn't find a screen for “${query}”. I can open listings, applications, issues, commission, organizations or your profile — or open a named property, application or issue.` };
}

export default function Assistant({ user, context, onCommand }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { id: 0, from: 'bot', text: `Hi ${user.name.split(' ')[0]}! Tell me what you want to do and I'll open it for you.` },
  ]);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, open]);

  const send = (text) => {
    const value = String(text || '').trim();
    if (!value) return;
    const intent = parseMessage(value, context, user);
    setMessages((current) => [...current, { id: Date.now(), from: 'user', text: value }, { id: Date.now() + 1, from: 'bot', text: intent?.reply || 'I can help you navigate.' }]);
    if (intent && intent.kind !== 'help') onCommand(intent);
    setInput('');
  };

  return <div className="assistant">
    {open && <section className="assistant-panel" role="dialog" aria-label="Navigation assistant">
      <div className="assistant-head"><div><div className="eyebrow">PROPMANAGER ASSISTANT</div><strong>Navigate by asking</strong></div><button aria-label="Close assistant" onClick={() => setOpen(false)}>×</button></div>
      <div className="assistant-messages">
        {messages.map((message) => <div key={message.id} className={`assistant-message ${message.from}`}>{message.text}</div>)}
        <div ref={endRef} />
      </div>
      <div className="assistant-suggestions">{SUGGESTIONS.map((item) => <button key={item} onClick={() => send(item)}>{item}</button>)}</div>
      <form className="assistant-input" onSubmit={(event) => { event.preventDefault(); send(input); }}>
        <input aria-label="Ask the assistant" value={input} onChange={(event) => setInput(event.target.value)} placeholder="e.g. show urgent issues" maxLength="200" />
        <button className="button button-dark" disabled={!input.trim()}>Send</button>
      </form>
    </section>}
    <button className="assistant-button" aria-label="Open navigation assistant" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? '×' : '✳'}</button>
  </div>;
}
