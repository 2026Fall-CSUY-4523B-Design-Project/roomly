import { useState } from "react";
import { BOROUGHS, formatAmenity } from "@/lib/format";

const AMENITIES = ["dishwasher", "laundry_in_building", "elevator"];
const number = value => value === "" ? null : Number(value);
const dollars = cents => cents == null ? "" : String(cents / 100);
const cents = value => value === "" ? null : Math.round(Number(value) * 100);

export default function FilterPanel({ initial, onApply, onReset }) {
  const [draft, setDraft] = useState(() => ({
    ...initial, minRent: dollars(initial.min_rent_cents), maxRent: dollars(initial.max_rent_cents),
    boroughs: initial.boroughs || [], amenities: initial.amenities || [],
  }));
  const [extra, setExtra] = useState("");
  const [options, setOptions] = useState(() => [...new Set([...AMENITIES, ...(initial.amenities || [])])]);
  function set(key, value) { setDraft(previous => ({ ...previous, [key]: value })); }
  function toggle(key, value) {
    const current = draft[key];
    set(key, current.includes(value) ? current.filter(item => item !== value) : [...current, value]);
  }
  function addAmenity() {
    const value = extra.trim().toLowerCase().replace(/\s+/g, "_");
    if (!value || draft.amenities.length >= 20) return;
    if (!options.includes(value)) setOptions([...options, value]);
    if (!draft.amenities.includes(value)) set("amenities", [...draft.amenities, value]);
    setExtra("");
  }
  function submit(event) {
    event.preventDefault();
    const { minRent, maxRent, ...criteria } = draft;
    onApply({
      ...criteria, min_rent_cents: cents(minRent), max_rent_cents: cents(maxRent),
      min_bedrooms: number(criteria.min_bedrooms ?? ""), max_bedrooms: number(criteria.max_bedrooms ?? ""),
      min_area_sqft: number(criteria.min_area_sqft ?? ""),
      move_in_from: criteria.move_in_from || null, move_in_to: criteria.move_in_to || null,
    });
  }
  return <form className="filters" onSubmit={submit} aria-label="Search filters">
    <fieldset><legend>Borough</legend>{BOROUGHS.map(({value, label}) =>
      <label className="check" key={value}><input type="checkbox" checked={draft.boroughs.includes(value)}
        onChange={() => toggle("boroughs", value)} />{label}</label>)}</fieldset>
    <fieldset><legend>Monthly rent ($)</legend><div className="row">
      <input type="number" min="0" step=".01" max={draft.maxRent || undefined} aria-label="Minimum rent" placeholder="Min"
        value={draft.minRent} onChange={e => set("minRent", e.target.value)} />
      <input type="number" min={draft.minRent || 0} step=".01" aria-label="Maximum rent" placeholder="Max"
        value={draft.maxRent} onChange={e => set("maxRent", e.target.value)} />
    </div></fieldset>
    <fieldset><legend>Bedrooms</legend><div className="row">
      <input type="number" aria-label="Minimum bedrooms" min="0" max={draft.max_bedrooms === "" ? 20 : draft.max_bedrooms ?? 20} placeholder="Min"
        value={draft.min_bedrooms ?? ""} onChange={e => set("min_bedrooms", e.target.value)} />
      <input type="number" aria-label="Maximum bedrooms" min={draft.min_bedrooms || 0} max="20" placeholder="Max"
        value={draft.max_bedrooms ?? ""} onChange={e => set("max_bedrooms", e.target.value)} />
    </div></fieldset>
    <fieldset><legend>Minimum area</legend>
      <input type="number" min="1" aria-label="Minimum area in square feet" placeholder="sq ft"
        value={draft.min_area_sqft ?? ""} onChange={e => set("min_area_sqft", e.target.value)} /></fieldset>
    <fieldset className="date-range"><legend>Move-in date</legend>
      <label>From <input type="date" max={draft.move_in_to || undefined} value={draft.move_in_from || ""} onChange={e => set("move_in_from", e.target.value)} /></label>
      <label>Through <input type="date" min={draft.move_in_from || undefined} value={draft.move_in_to || ""} onChange={e => set("move_in_to", e.target.value)} /></label>
    </fieldset>
    <fieldset><legend>Amenities</legend>{options.map(value =>
      <label key={value} className="check"><input type="checkbox" checked={draft.amenities.includes(value)}
        disabled={draft.amenities.length >= 20 && !draft.amenities.includes(value)} onChange={() => toggle("amenities", value)} />{formatAmenity(value)}</label>)}
      <div className="row add-amenity">
        <input aria-label="Other amenity" placeholder="Other amenity" value={extra} onChange={e => setExtra(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addAmenity(); } }} />
        <button className="button secondary" type="button" disabled={!extra.trim() || draft.amenities.length >= 20} onClick={addAmenity}>Add</button>
      </div>
    </fieldset>
    <label className="check"><input type="checkbox" checked={!!draft.no_broker_fee} onChange={e => set("no_broker_fee", e.target.checked)} />No broker fee</label>
    {draft.south != null && <p className="muted">Saved map bounds apply.</p>}
    <div className="row filter-actions"><button className="button">Apply filters</button><button className="button secondary" type="button" onClick={onReset}>Reset</button></div>
  </form>;
}
