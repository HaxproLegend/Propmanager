import React, { useEffect, useState } from 'react';
import { Empty, SectionTitle, Skeleton, Stats, money } from './ui.jsx';

const COLORS = ['#315a45', '#76a078', '#c98a55', '#7b9a7c', '#9d3d35', '#6e8ca0', '#b0a06a', '#8b7aa8'];

function BarList({ data, format = (value) => value }) {
  if (!data?.length) return <Empty text="No data yet." />;
  const max = Math.max(...data.map((item) => item.value), 1);
  return <div className="bar-list">{data.map((item, index) => <div className="bar-item" key={item.label}>
    <div className="bar-label"><span>{item.label}</span><strong>{format(item.value)}</strong></div>
    <div className="bar-track"><div style={{ width: `${Math.max(3, 100 * item.value / max)}%`, background: COLORS[index % COLORS.length] }} /></div>
  </div>)}</div>;
}

function Donut({ data, format = (value) => value }) {
  const total = data?.reduce((sum, item) => sum + item.value, 0) || 0;
  if (!data?.length || !total) return <Empty text="No data yet." />;
  let offset = 0;
  const stops = data.map((item, index) => {
    const start = offset;
    offset += 100 * item.value / total;
    return `${COLORS[index % COLORS.length]} ${start}% ${offset}%`;
  }).join(',');
  return <div className="donut-wrap"><div className="donut" style={{ background: `conic-gradient(${stops})` }}><div><strong>{total}</strong><small>total</small></div></div>
    <ul className="legend">{data.map((item, index) => <li key={item.label}><span style={{ background: COLORS[index % COLORS.length] }} />{item.label}<b>{format(item.value)}</b></li>)}</ul>
  </div>;
}

function Trend({ data, format = (value) => value }) {
  if (!data?.length) return <Empty text="No monthly trend yet." />;
  const values = data.map((item) => item.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const points = data.map((item, index) => {
    const x = data.length === 1 ? 50 : 4 + 92 * index / (data.length - 1);
    const y = 86 - 70 * (item.value - min) / range;
    return `${x},${y.toFixed(1)}`;
  }).join(' ');
  return <div className="trend"><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Monthly trend"><line x1="0" y1="86" x2="100" y2="86" className="trend-axis" /><polyline points={points} className="trend-line" />{data.map((item, index) => { const x = data.length === 1 ? 50 : 4 + 92 * index / (data.length - 1); const y = 86 - 70 * (item.value - min) / range; return <circle key={item.label} cx={x} cy={y.toFixed(1)} r="2.2" className="trend-dot"><title>{item.label}: {format(item.value)}</title></circle>; })}</svg>
    <div className="trend-labels">{data.map((item) => <span key={item.label}>{item.label}</span>)}</div>
  </div>;
}

export default function Analytics({ user, request, notify }) {
  const [data, setData] = useState(null);
  const [detailed, setDetailed] = useState(false);
  useEffect(() => {
    request('/api/analytics').then(setData).catch((err) => notify(err.message, 'error'));
  }, [request, notify]);

  if (!data) return <Skeleton count={4} />;
  const chart = (key) => data.charts[key] || [];
  const moneyValue = (value) => money(value / 100);
  const kpis = data.kpis.map((item) => [item.label, typeof item.value === 'number' && /commission/i.test(item.label) ? money(item.value) : item.value]);
  const occupancy = data.kpis.find((item) => item.label === 'Occupancy');

  return <div>
    <div className="page-head"><div className="eyebrow">DEEP DIVE · ANALYTICS</div><h1>Numbers behind the workspace</h1><p>One minimal view for the shapes of your portfolio, with a detailed table when you need the raw numbers.</p></div>
    <div className="analytics-toolbar"><button className={`chip ${detailed ? 'active' : ''}`} onClick={() => setDetailed(!detailed)}>{detailed ? 'Hide detail' : 'Show detailed tables'}</button><span>Scoped to your {user.role} account</span></div>
    <Stats items={kpis} />

    <div className="analytics-grid">
      <section className="dash-section"><SectionTitle title="Applications" sub="Decisions and monthly volume." /><Donut data={chart('applications_by_status')} /><div className="chart-divider" /><SectionTitle title="Applications per month" /><Trend data={chart('applications_by_month')} /></section>

      <section className="dash-section"><SectionTitle title="Issues by status" sub="How the queue is moving." /><BarList data={chart('tickets_by_status')} /><div className="chart-divider" /><SectionTitle title="Importance mix" /><BarList data={chart('tickets_by_priority')} /></section>

      <section className="dash-section"><SectionTitle title="Property mix" sub="Apartments, PGs and offices in scope." /><Donut data={chart('properties_by_type')} />{occupancy && <><div className="chart-divider" /><SectionTitle title="Unit occupancy" /><div className="occupancy-bar"><div style={{ width: occupancy.value }} /></div><small className="chart-note">{occupancy.value} of units are rented</small></>}</section>

      <section className="dash-section"><SectionTitle title="Commission by month" sub="Obligations recorded, not collected." /><Trend data={chart('commissions_by_month')} format={moneyValue} /><div className="chart-divider" /><SectionTitle title="Ledger status" /><BarList data={chart('commissions_by_status')} format={moneyValue} /></section>

      {user.role === 'broker' && <>
        <section className="dash-section"><SectionTitle title="Lead pipeline" sub="Owner and tenant enquiries by stage." /><BarList data={chart('leads_by_status')} /></section>
        <section className="dash-section"><SectionTitle title="Issue categories" sub="What residents report most." /><BarList data={chart('tickets_by_category')} /></section>
      </>}
    </div>

    <section className="dash-section"><SectionTitle title="Monthly numbers" sub="Applications, new issues and commission obligations by billing month." />{data.monthly.length ? <div className="list-table">{data.monthly.map((row) => <div className="data-row" key={row.month}><div><strong>{row.month}</strong><small>{row.applications} applications · {row.issues} issues</small></div><b>{money(row.commission_paise / 100)}</b></div>)}</div> : <Empty text="No monthly activity yet." />}</section>

    {detailed && <>
      <section className="dash-section"><SectionTitle title="Property detail" sub="Unit counts, occupancy and open issues for each listing." />{data.properties.length ? <div className="list-table">{data.properties.map((row) => <div className="data-row" key={row.id}><div><strong>{row.title}</strong><small>{row.property_type} · {row.status}</small></div><span>{row.occupied}/{row.unit_count} units</span><span>{row.open_issues} open issues</span></div>)}</div> : <Empty text="No properties in scope." />}</section>
      <section className="dash-section"><SectionTitle title="How these numbers are calculated" sub="Plain definitions so nobody has to guess." /><ul className="definition-list"><li><strong>Occupancy</strong> — rented units divided by all units in scoped properties.</li><li><strong>Commission obligations</strong> — sum of monthly ledger entries at the rate active for that billing month.</li><li><strong>Monthly volume</strong> — records grouped by the month they were created.</li><li><strong>Similar reports</strong> in the queue are decision support only; there is no automated score.</li></ul></section>
    </>}
  </div>;
}
