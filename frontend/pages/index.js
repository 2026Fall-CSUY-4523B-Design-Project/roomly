import Head from "next/head";
import { useEffect, useRef, useState } from "react";

import ListingCard from "@/components/ListingCard";
import SprintNotice from "@/components/SprintNotice";
import { api } from "@/lib/api";
import { BOROUGHS, dollarsToCents, plural } from "@/lib/format";

import styles from "@/styles/search.module.css";

const SORTS = [
  { value: "newest", label: "Newest first" },
  { value: "rent_asc", label: "Rent: low to high" },
  { value: "rent_desc", label: "Rent: high to low" },
];

const EMPTY_FILTERS = { boroughs: [], maxRent: "", minBedrooms: "", noBrokerFee: false, sort: "newest" };

// Search (§8.1.2.5, R-3.1): hard constraints only. A listing whose value is Unknown fails any
// active constraint on that value, so filters never surface guesses.
export default function SearchPage() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [rentError, setRentError] = useState(null);
  const [result, setResult] = useState({ state: "loading", page: null, error: null });
  const latest = useRef(0); // a slow early response must not overwrite a newer one

  async function runSearch(next) {
    const maxRent = dollarsToCents(next.maxRent);
    if (Number.isNaN(maxRent)) {
      setRentError("Enter an amount in dollars, like 3200");
      return;
    }
    setRentError(null);
    const seq = ++latest.current;
    setResult((r) => ({ ...r, state: "loading", error: null }));
    try {
      const page = await api.search({
        borough: next.boroughs,
        max_rent_cents: maxRent,
        min_bedrooms: next.minBedrooms,
        no_broker_fee: next.noBrokerFee,
        sort: next.sort,
        limit: 24,
      });
      if (seq === latest.current) setResult({ state: "done", page, error: null });
    } catch (err) {
      if (seq === latest.current) setResult({ state: "error", page: null, error: err });
    }
  }

  useEffect(() => {
    runSearch(EMPTY_FILTERS);
  }, []);

  function update(patch, { now = false } = {}) {
    const next = { ...filters, ...patch };
    setFilters(next);
    if (now) runSearch(next);
  }

  function toggleBorough(value) {
    const boroughs = filters.boroughs.includes(value)
      ? filters.boroughs.filter((b) => b !== value)
      : [...filters.boroughs, value];
    update({ boroughs }, { now: true });
  }

  const active =
    filters.boroughs.length > 0 || filters.maxRent !== "" || filters.minBedrooms !== "" || filters.noBrokerFee;

  return (
    <>
      <Head>
        <title>Search · Roomly</title>
      </Head>
      <section className={styles.hero}>
        <div className="container">
          <p className="eyebrow">New York City · leases of 30 days or more</p>
          <h1 className={styles.headline}>
            Find a place that works <em>for everyone</em>.
          </h1>
          <p className="lede">
            Every listing in one view, every unknown labeled as unknown, and a shared room where your group
            compares, votes and decides.
          </p>
        </div>
      </section>

      <div className="container">
        <form
          className={`card ${styles.filters}`}
          onSubmit={(e) => {
            e.preventDefault();
            runSearch(filters);
          }}
        >
          <fieldset className={styles.boroughs}>
            <legend className="label">Borough</legend>
            <div className="row" style={{ gap: 8 }}>
              {BOROUGHS.map((b) => (
                <button
                  key={b.value}
                  type="button"
                  className="chip"
                  aria-pressed={filters.boroughs.includes(b.value)}
                  onClick={() => toggleBorough(b.value)}
                >
                  {b.label}
                </button>
              ))}
            </div>
          </fieldset>
          <div className={styles.controls}>
            <div className="field">
              <label htmlFor="max-rent">Max rent / month</label>
              <input
                id="max-rent"
                className="input"
                inputMode="decimal"
                placeholder="Any"
                value={filters.maxRent}
                aria-invalid={rentError ? "true" : undefined}
                onChange={(e) => update({ maxRent: e.target.value })}
              />
              {rentError ? <span className="error-text">{rentError}</span> : null}
            </div>
            <div className="field">
              <label htmlFor="min-bedrooms">Bedrooms</label>
              <select
                id="min-bedrooms"
                className="select"
                value={filters.minBedrooms}
                onChange={(e) => update({ minBedrooms: e.target.value }, { now: true })}
              >
                <option value="">Any</option>
                <option value="0">Studio or more</option>
                <option value="1">1+</option>
                <option value="2">2+</option>
                <option value="3">3+</option>
                <option value="4">4+</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="sort">Sort</label>
              <select
                id="sort"
                className="select"
                value={filters.sort}
                onChange={(e) => update({ sort: e.target.value }, { now: true })}
              >
                {SORTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <label className={`check ${styles.fee}`}>
              <input
                type="checkbox"
                checked={filters.noBrokerFee}
                onChange={(e) => update({ noBrokerFee: e.target.checked }, { now: true })}
              />
              No broker fee
            </label>
            <div className={styles.actions}>
              {active ? (
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => {
                    setFilters(EMPTY_FILTERS);
                    runSearch(EMPTY_FILTERS);
                  }}
                >
                  Clear
                </button>
              ) : null}
              <button type="submit" className="btn btn-primary">
                Search
              </button>
            </div>
          </div>
        </form>

        <section className={styles.results} aria-live="polite" aria-busy={result.state === "loading"}>
          <Results result={result} filtered={active} />
        </section>

        <div className={styles.roadmap}>
          <SprintNotice
            sprint={4}
            compact
            title="Map, commute times and ranking"
            items={[
              "Map view with a draggable viewport (the API already filters by south/west/north/east)",
              "Commute time to up to three saved destinations",
              "Ranked results that explain each score",
            ]}
          />
        </div>
      </div>
    </>
  );
}

function Results({ result, filtered }) {
  if (result.state === "error") {
    return (
      <div className="alert alert-error" role="alert">
        {result.error.message}
      </div>
    );
  }
  if (!result.page) {
    return (
      <div className="grid-cards" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className="skeleton" style={{ minHeight: 230 }} />
        ))}
      </div>
    );
  }
  const { items, total } = result.page;
  if (total === 0) {
    return filtered ? (
      <div className="empty">
        <h3>Nothing matches every filter</h3>
        <p>Listings with an Unknown value don&rsquo;t pass a filter on that value. Try loosening one.</p>
      </div>
    ) : (
      <div className="empty">
        <h3>No listings yet</h3>
        <p>
          Listings appear here once the SampleFeed source is collected, or when someone submits one with{" "}
          <code>POST /listings</code>.
        </p>
      </div>
    );
  }
  return (
    <>
      <p className={styles.count}>
        {plural(total, "listing")}
        {total > items.length ? ` · showing the first ${items.length}` : ""}
      </p>
      <div className="grid-cards" style={{ opacity: result.state === "loading" ? 0.55 : 1 }}>
        {items.map((listing) => (
          <ListingCard key={listing.id} listing={listing} />
        ))}
      </div>
    </>
  );
}
