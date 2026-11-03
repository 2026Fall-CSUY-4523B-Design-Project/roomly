import Head from "next/head";
import { useEffect, useState } from "react";

import FilterPanel, { EMPTY_FILTERS, toSearchParams } from "@/components/FilterPanel";
import Header from "@/components/Header";
import ListingCard from "@/components/ListingCard";
import { searchListings } from "@/lib/api";

const SORTS = [
  { value: "newest", label: "Newest" },
  { value: "rent_asc", label: "Rent: low to high" },
  { value: "rent_desc", label: "Rent: high to low" },
];

// Dashboard: search filters on the left, matching listings on the right (UC-3, R-3.1). Guests allowed.
export default function Dashboard() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | ready | error

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    searchListings(toSearchParams(filters), { sort })
      .then((result) => {
        if (cancelled) return;
        setPage(result);
        setStatus("ready");
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, [filters, sort]);

  return (
    <>
      <Head>
        <title>Roomly · Find a place together</title>
      </Head>
      <Header />

      <main className="dashboard">
        <aside>
          <h2>Filters</h2>
          <FilterPanel initial={filters} onApply={setFilters} />
        </aside>

        <section aria-labelledby="results-heading">
          <div className="results-bar">
            <h2 id="results-heading">
              {status === "ready" ? `${page.total} listing${page.total === 1 ? "" : "s"}` : "Listings"}
            </h2>
            <label>
              Sort{" "}
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                {SORTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {status === "loading" && <p className="muted">Loading listings…</p>}
          {status === "error" && <p className="error">Could not load listings. Is the backend running on :8000?</p>}
          {status === "ready" && page.items.length === 0 && <p className="muted">No listings match these filters.</p>}
          {status === "ready" && (
            <div className="grid">
              {page.items.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          )}
        </section>
      </main>
    </>
  );
}
