import React, { useEffect, useState } from 'react';
import { Badge, Drawer, Empty, ListingImage, SectionTitle, Skeleton, money } from './ui.jsx';

const TYPES = ['Apartment', 'PG/Hostel', 'Office/Commercial'];
const STATUSES = ['Available', 'Unavailable', 'Rented'];

export default function ListingExplorer({ properties, applications, request, act, busy, notify, ownerMode, onChanged, focus }) {
  const [results, setResults] = useState(properties);
  const [filters, setFilters] = useState({ q: '', location: '', property_type: '', min_rent: '', max_rent: '', status: '' });
  const [selected, setSelected] = useState(null);
  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(false);
  const [unitId, setUnitId] = useState('');

  useEffect(() => { setResults(properties); }, [properties]);

  const search = async (event) => {
    event?.preventDefault();
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
    setLoading(true);
    try {
      const data = await request(`/api/properties?${params.toString()}`);
      setResults(data.properties);
    } catch (err) { notify(err.message, 'error'); }
    finally { setLoading(false); }
  };

  const openDetail = async (property) => {
    setSelected(property); setUnitId(''); setUnits([]);
    try { const data = await request(`/api/properties/${property.id}/units`); setUnits(data.units); }
    catch (err) { notify(err.message, 'error'); }
  };

  useEffect(() => {
    if (!focus?.id) return;
    const property = properties.find((item) => item.id === focus.id);
    if (property) openDetail(property);
  }, [focus?.nonce]);

  const apply = (property) => {
    const payload = { property_id: property.id };
    if (unitId) payload.unit_id = Number(unitId);
    act(() => request('/api/applications', { method: 'POST', body: JSON.stringify(payload) }), `Application sent for ${property.title}.`);
    setSelected(null); onChanged?.();
  };

  const appliedIds = new Set(applications.map((application) => application.property_id));

  return <section className="dash-section listing-explorer">
    <SectionTitle title={ownerMode ? 'My listings' : 'Homes available'} sub={ownerMode ? 'Every property and its unit inventory in one place.' : 'Browse available homes, rooms and offices.'} />
    <form className="filter-bar" onSubmit={search}>
      <input aria-label="Search listings" placeholder="Search by name or keyword" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
      <input aria-label="Filter by location" placeholder="Area or city" value={filters.location} onChange={(e) => setFilters({ ...filters, location: e.target.value })} />
      <select aria-label="Filter by property type" value={filters.property_type} onChange={(e) => setFilters({ ...filters, property_type: e.target.value })}><option value="">All types</option>{TYPES.map((type) => <option key={type}>{type}</option>)}</select>
      <input aria-label="Minimum rent" type="number" min="0" placeholder="Min rent" value={filters.min_rent} onChange={(e) => setFilters({ ...filters, min_rent: e.target.value })} />
      <input aria-label="Maximum rent" type="number" min="0" placeholder="Max rent" value={filters.max_rent} onChange={(e) => setFilters({ ...filters, max_rent: e.target.value })} />
      {ownerMode && <select aria-label="Filter by status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}><option value="">Any status</option>{STATUSES.map((status) => <option key={status}>{status}</option>)}</select>}
      <button className="button button-dark" disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
      <button type="button" className="button button-light" onClick={() => { setFilters({ q: '', location: '', property_type: '', min_rent: '', max_rent: '', status: '' }); setResults(properties); }}>Clear</button>
    </form>
    {loading ? <Skeleton count={3} /> : results.length ? <div className="listing-grid">
      {results.map((property) => <article className="listing-card" key={property.id}>
        <button className="listing-image-button" onClick={() => openDetail(property)}><ListingImage src={property.image_url} alt={property.title}>{property.property_type}</ListingImage><span className="image-index">{property.property_type} · {property.unit_count} units</span></button>
        <div className="listing-content"><div className="listing-rent">{money(property.monthly_rent)} <small>/ month</small></div><h3>{property.title}</h3><p>{property.address}</p><p className="listing-desc">{property.description || 'A rental listing managed through PropManager.'}</p>
          <div className="listing-actions"><button className="button button-light" onClick={() => openDetail(property)}>View details →</button>
            {!ownerMode && <button className="button button-dark" disabled={busy || appliedIds.has(property.id)} onClick={() => act(() => request('/api/applications', { method: 'POST', body: JSON.stringify({ property_id: property.id }) }), `Application sent for ${property.title}.`)}>{appliedIds.has(property.id) ? 'Applied' : 'Apply'}</button>}
            {ownerMode && <Badge value={property.status} />}
          </div>
        </div>
      </article>)}
    </div> : <Empty text="No listings match these filters." />}

    <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.title || ''} sub={selected?.address} wide>
      {selected && <>
        <ListingImage src={selected.image_url} alt={selected.title} className="drawer-image">{selected.property_type}</ListingImage>
        <div className="detail-meta"><Badge value={selected.status} /><Badge value={selected.property_type} /><span>{money(selected.monthly_rent)} / month</span></div>
        <p className="detail-description">{selected.description || 'Managed through PropManager with broker coordination.'}</p>
        <SectionTitle title="Units and rooms" sub={`${units.filter((unit) => unit.status === 'Available').length} of ${units.length} available`} />
        {units.length ? <div className="unit-list">{units.map((unit) => <div className="unit-row" key={unit.id}><strong>{unit.unit_label}</strong><small>{money(unit.monthly_rent)} / month</small><Badge value={unit.status} /></div>)}</div> : <Empty text="Unit details will appear here." />}
        {!ownerMode && <div className="drawer-cta"><label className="form-field">Apply for a unit<select value={unitId} onChange={(e) => setUnitId(e.target.value)}><option value="">First available unit</option>{units.filter((unit) => unit.status === 'Available').map((unit) => <option value={unit.id} key={unit.id}>{unit.unit_label}</option>)}</select></label><button className="button button-dark" disabled={busy || appliedIds.has(selected.id)} onClick={() => apply(selected)}>{appliedIds.has(selected.id) ? 'Already applied' : 'Apply through broker →'}</button></div>}
      </>}
    </Drawer>
  </section>;
}

export function CompactListingGrid({ properties, title = 'My Properties', sub }) {
  return <section className="dash-section"><SectionTitle title={title} sub={sub} />{properties.length ? <div className="listing-grid">{properties.map((property) => <article className="listing-card" key={property.id}><ListingImage src={property.image_url} alt={property.title}>{property.property_type}</ListingImage><div className="listing-content"><div className="listing-rent">{money(property.monthly_rent)} <small>/ month</small></div><h3>{property.title}</h3><p>{property.address}</p><Badge value={property.status} /></div></article>)}</div> : <Empty text="Nothing here yet." />}</section>;
}
