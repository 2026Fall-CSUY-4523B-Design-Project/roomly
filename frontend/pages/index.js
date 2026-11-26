import Head from "next/head";
import { useEffect, useRef, useState } from "react";

import FilterPanel from "@/components/FilterPanel";
import Link from "next/link";
import SavedSearches from "@/components/SavedSearches";
import { useAuth } from "@/lib/auth";
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
  const { user, loading } = useAuth();
  // Remount on sign-in/out so one user's applied filters and saved search never leak to the next.
  // Wait for the session to resolve first so signed-in users don't fetch twice on load.
  return <Search key={loading ? "pending" : user?.id || "guest"} user={user} />;
}

const PAGE_SIZE = 20;
function Search({ user }) {
  const { authenticatedRequest, loading } = useAuth();
  const [filters, setFilters] = useState({});
  const [saved, setSaved] = useState(null);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [retry, setRetry] = useState(0);
  const resultsTop = useRef(null);
  function apply(criteria, item = null) {
    setFilters(criteria);
    setSaved(item);
    setOffset(0);
    setRevision(value => value + 1);
    setNotice("");
  }
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [notice, setNotice] = useState("");

  function goToPage(next) {
    setOffset(next);
    resultsTop.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  useEffect(() => {
    if (loading) return undefined;
    let cancelled = false;
    setStatus("loading");
    const { boroughs, amenities, ...other } = filters;
    const resultPage = saved
      ? authenticatedRequest(`/saved-searches/${saved.id}/results?sort=${sort}&limit=${PAGE_SIZE}&offset=${offset}`)
      : searchListings({ ...other, borough: boroughs, amenity: amenities }, { sort, limit: PAGE_SIZE, offset });
    resultPage
      .then((result) => {
        if (cancelled) return;
        if (offset && offset >= result.total) {
          setOffset(Math.max(0, Math.floor((result.total - 1) / PAGE_SIZE) * PAGE_SIZE));
          return;
        }
        setPage(result);
        setStatus("ready");
      })
      .catch((error) => {
        if (cancelled) return;
        // The saved search was deleted elsewhere: fall back to its criteria as an ordinary search.
        if (saved && error.status === 404) {
          setNotice(`“${saved.name}” no longer exists, so its filters are shown as a regular search.`);
          setSaved(null);
          return;
        }
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [filters, sort, offset, saved, authenticatedRequest, revision, retry, loading]);

  return (
    <>
      <Head>
        <title>Roomly · Find a place together</title>
      </Head>
      <Header />

      <main className="dashboard">
        <aside>
          <h2>Filters</h2>
          <FilterPanel key={revision} initial={filters} onApply={apply} onReset={() => apply({})} />
          {user ? <SavedSearches criteria={filters} activeId={saved?.id} onOpen={item => apply(item.criteria, item)}
            onDelete={id => { if (saved?.id === id) setSaved(null); }} /> :
            !loading && <p className="save-prompt"><Link href="/sign-in"><a>Sign in</a></Link> to save searches and get alerts for new matches.</p>}
        </aside>

        <section aria-labelledby="results-heading" ref={resultsTop} className="results">
          {notice && <p role="status" className="muted">{notice}</p>}
          {saved && <p>Saved search · <strong>{saved.name}</strong></p>}
          <div className="results-bar">
            <h2 id="results-heading">
              {status === "ready" ? `${page.total} listing${page.total === 1 ? "" : "s"}` : "Listings"}
            </h2>
            <label>
              Sort{" "}
              <select value={sort} onChange={(e) => { setSort(e.target.value); setOffset(0); }}>
                {SORTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {status === "loading" && <p role="status" className="muted">Loading listings…</p>}
          {status === "error" && <p role="alert" className="error">Could not load listings. <button className="link-button" onClick={() => setRetry(value => value + 1)}>Try again</button></p>}
          {status === "ready" && page.items.length === 0 && <p className="muted">No listings match these filters.</p>}
          {status === "ready" && (
            <div className="grid">
              {page.items.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          )}
          {status === "ready" && page.offset === offset && page.total > PAGE_SIZE && <nav className="search-pager" aria-label="Search pages">
            <button className="button secondary" disabled={!offset} onClick={() => goToPage(offset - PAGE_SIZE)}>Previous</button>
            <span>Page {Math.floor(offset / PAGE_SIZE) + 1} of {Math.ceil(page.total / PAGE_SIZE)}</span>
            <button className="button secondary" disabled={offset + PAGE_SIZE >= page.total} onClick={() => goToPage(offset + PAGE_SIZE)}>Next</button>
          </nav>}
        </section>
      </main>
    </>
  );
}
