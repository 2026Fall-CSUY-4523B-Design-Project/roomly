import { useState } from "react";

import { BOROUGHS } from "@/lib/format";

export const EMPTY_FILTERS = { borough: [], minRent: "", maxRent: "", minBedrooms: "", noBrokerFee: false };

// Turns the form state into /search query parameters. Rents are typed in dollars and sent in cents.
export function toSearchParams(f) {
  const cents = (dollars) => (dollars === "" ? null : Math.round(Number(dollars) * 100));
  return {
    borough: f.borough,
    min_rent_cents: cents(f.minRent),
    max_rent_cents: cents(f.maxRent),
    min_bedrooms: f.minBedrooms,
    no_broker_fee: f.noBrokerFee || null,
  };
}

// Hard-constraint filters (R-3.1). Applied on submit, so typing does not fire a search per keystroke.
export default function FilterPanel({ initial = EMPTY_FILTERS, onApply }) {
  const [f, setF] = useState(initial);
  const set = (key) => (e) => setF({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  function toggleBorough(value) {
    const borough = f.borough.includes(value) ? f.borough.filter((b) => b !== value) : [...f.borough, value];
    setF({ ...f, borough });
  }

  function submit(e) {
    e.preventDefault();
    onApply(f);
  }

  function reset() {
    setF(EMPTY_FILTERS);
    onApply(EMPTY_FILTERS);
  }

  return (
    <form className="filters" onSubmit={submit} aria-label="Search filters">
      <fieldset>
        <legend>Borough</legend>
        {BOROUGHS.map((b) => (
          <label key={b.value} className="check">
            <input type="checkbox" checked={f.borough.includes(b.value)} onChange={() => toggleBorough(b.value)} />
            {b.label}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Monthly rent ($)</legend>
        <div className="row">
          <input type="number" min="0" placeholder="Min" aria-label="Minimum rent" value={f.minRent} onChange={set("minRent")} />
          <input type="number" min="0" placeholder="Max" aria-label="Maximum rent" value={f.maxRent} onChange={set("maxRent")} />
        </div>
      </fieldset>

      <fieldset>
        <legend>Bedrooms</legend>
        <select aria-label="Minimum bedrooms" value={f.minBedrooms} onChange={set("minBedrooms")}>
          <option value="">Any</option>
          <option value="0">Studio+</option>
          <option value="1">1+</option>
          <option value="2">2+</option>
          <option value="3">3+</option>
          <option value="4">4+</option>
        </select>
      </fieldset>

      <label className="check">
        <input type="checkbox" checked={f.noBrokerFee} onChange={set("noBrokerFee")} />
        No broker fee
      </label>

      <div className="row">
        <button type="submit" className="button">Apply</button>
        <button type="button" className="button secondary" onClick={reset}>Reset</button>
      </div>
    </form>
  );
}
