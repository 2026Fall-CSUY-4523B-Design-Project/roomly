import Head from "next/head";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import SaveComparison from "@/components/SaveComparison";
import GroupPicker from "@/components/GroupPicker";
import Header from "@/components/Header";
import { previewComparison } from "@/lib/api";
import { comparisonRows, comparisonTitle, useComparison } from "@/lib/comparison";
import { UNKNOWN, formatListingValue } from "@/lib/format";

const cellText = (row, cell) => cell?.known && cell.value != null ? formatListingValue(row.key, cell.value) : UNKNOWN;

function SelectionList({ items, missingId, onRemove }) {
  return <ul className="comparison-state-list">{items.map((item) => <li key={item.id}>
    <Link href={`/listings/${item.id}`}><a>{item.title}</a></Link>
    {item.id === missingId && <span className="tag warn">No longer available</span>}
    <button type="button" className="button secondary" onClick={() => onRemove(item.id)}
      aria-label={`Remove ${item.title} from comparison`}>Remove</button>
  </li>)}</ul>;
}

export default function Compare() {
  const { selected, ready, remove } = useComparison();
  const [result, setResult] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [onlyDifferences, setOnlyDifferences] = useState(false);
  const region = useRef(null);
  const selectionKey = JSON.stringify(selected.map((item) => item.id));

  useEffect(() => {
    const ids = JSON.parse(selectionKey);
    if (!ready || ids.length < 2) return;
    let cancelled = false;
    // Keep the previous table on screen while refreshing; only clear a stale error.
    setResult((previous) => previous?.error ? null : previous);
    previewComparison(ids).then((table) => {
      if (!cancelled) setResult({ key: selectionKey, table });
    }).catch((error) => {
      if (!cancelled) setResult({ key: selectionKey, error });
    });
    return () => { cancelled = true; };
  }, [ready, selectionKey, attempt]);

  const ids = selected.map((item) => item.id);
  const refreshing = result?.key !== selectionKey;
  const error = !refreshing ? result?.error : null;
  // A previous table can stand in while refreshing only if it covers every selected listing.
  const covers = result?.table && ids.every((id) => result.table.listings.some((listing) => listing.id === id));
  const table = covers ? result.table : null;
  const listings = table ? ids.map((id) => table.listings.find((listing) => listing.id === id)) : [];
  const allRows = table ? comparisonRows(table) : [];
  const rows = onlyDifferences
    ? allRows.filter((row) => new Set(listings.map((listing) => cellText(row, row.cells.find((cell) => cell.listing_id === listing.id)))).size > 1)
    : allRows;
  const hiddenCount = allRows.length - rows.length;
  const missingId = error?.status === 404 ? ids.find((id) => error.message.includes(id)) : undefined;
  const missing = selected.find((item) => item.id === missingId);

  function removeFromTable(id) {
    remove(id);
    region.current?.focus();
  }

  return <>
    <Head><title>Compare listings · Roomly</title></Head>
    <Header />
    <main className="comparison-page">
      <Link href="/"><a className="back-link">← Back to listings</a></Link>
      <div className="comparison-title">
        <h1>Compare listings</h1>
        <Link href="/comparisons"><a className="button secondary">My comparisons</a></Link>
      </div>
      {!ready ? <p role="status">Loading selection…</p> : selected.length < 2 ? (
        <section className="card comparison-state">
          <h2>{selected.length ? "Choose one more listing" : "No listings selected"}</h2>
          <p>{selected.length
            ? "Comparisons need at least two listings. Add another from search or a listing page."
            : "Use the Compare button on a search result or listing page to add listings."}</p>
          {selected.length > 0 && <SelectionList items={selected} onRemove={remove} />}
          <Link href="/"><a className="button">Browse listings</a></Link>
        </section>
      ) : error ? (
        <section className="card comparison-state">
          <h2>Could not load comparison</h2>
          <p role="alert">{missing
            ? `“${missing.title}” is no longer available. Remove it to compare the rest.`
            : error.status === 404
              ? "A selected listing no longer exists. Remove it from your selection or choose other listings."
              : "Something went wrong. Try again, or change your selection below."}</p>
          <SelectionList items={selected} missingId={missingId} onRemove={remove} />
          <button type="button" className="button" onClick={() => setAttempt((n) => n + 1)}>Try again</button>
        </section>
      ) : !table ? <p role="status">Loading comparison…</p> : <>
        <div className="comparison-toolbar">
          <label>
            <input type="checkbox" checked={onlyDifferences} onChange={(event) => setOnlyDifferences(event.target.checked)} />
            {" "}Only show differences
          </label>
          <span role="status" className="muted">
            {refreshing ? "Updating comparison…" : onlyDifferences && hiddenCount ? `${hiddenCount} identical ${hiddenCount === 1 ? "row" : "rows"} hidden` : ""}
          </span>
          <div className="comparison-share">
            <SaveComparison key={selectionKey} ids={ids} />
            <GroupPicker label="Share to group" confirmLabel="Share and discuss" withTitle
              onConfirm={async (request, groupId, { title }) => {
                const saved = await request("/comparisons", { method: "POST", body: { listing_ids: ids, group_id: groupId, title } });
                return { pathname: "/groups/[id]", query: { id: groupId, comparison: saved.id } };
              }} />
          </div>
        </div>
        <div ref={region} className={`comparison-table-wrap${refreshing ? " refreshing" : ""}`} role="region"
          aria-label="Listing comparison table" aria-busy={refreshing} tabIndex={0}>
          <table className="comparison-table">
            <caption className="visually-hidden">
              Comparison of {listings.length} listings. Cells marked Best have the best value in their row.
            </caption>
            <thead><tr><th scope="col">Attribute</th>{listings.map((listing) => <th scope="col" key={listing.id}>
              <Link href={`/listings/${listing.id}`}><a>{comparisonTitle(listing)}</a></Link>
              {(listing.is_synthetic || listing.has_conflicts) && <div className="comparison-tags">
                {listing.is_synthetic && <span className="tag">Synthetic</span>}
                {listing.has_conflicts && <span className="tag warn">Conflicting sources</span>}
              </div>}
              <button type="button" className="button secondary" onClick={() => removeFromTable(listing.id)}
                aria-label={`Remove ${comparisonTitle(listing)} from comparison`}>Remove</button>
            </th>)}</tr></thead>
            <tbody>{rows.length ? rows.map((row) => <tr key={row.key}>
              <th scope="row">{row.label}{row.formula && <small className="comparison-hint">{row.formula}</small>}{row.direction && <span className="comparison-hint">{row.direction === "lower" ? "Lower" : "Higher"} is better</span>}</th>
              {listings.map((listing) => {
                const cell = row.cells.find((item) => item.listing_id === listing.id);
                const best = cell?.known && cell.value != null && cell.best && !refreshing;
                return <td key={listing.id} className={best ? "comparison-best" : undefined}>
                  {cellText(row, cell)}
                  {best && <span className="comparison-best-label">Best</span>}
                </td>;
              })}
            </tr>) : <tr><td colSpan={listings.length + 1} className="muted">These listings match on every attribute.</td></tr>}</tbody>
          </table>
        </div>
        {table.notes.map((note, index) => <p className="muted" key={index}>{note}</p>)}
      </>}
    </main>
  </>;
}
