import Link from "next/link";
import { comparisonRows, comparisonTitle } from "@/lib/comparison";
import { UNKNOWN, formatListingValue } from "@/lib/format";

// Collapsible inside a group room; `standalone` renders the body flat for its own page,
// where the page heading already carries the title.
export default function SavedComparisonTable({ comparison, standalone = false }) {
  const { listings, notes } = comparison.table;
  const rows = comparisonRows(comparison.table);
  const name = comparison.title || (comparison.group_id ? "Shared comparison" : "Saved comparison");
  const titleOf = listingId => {
    const listing = listings.find(item => item.id === listingId);
    return listing ? comparisonTitle(listing) : "A listing";
  };
  const changes = comparison.changes.filter(change => change.state !== "unchanged");
  const body = <>
    {changes.length > 0 && <ul className="group-changes" aria-label="Changes since this comparison was saved">{changes.map(change => <li key={change.listing_id}>
      <strong>{titleOf(change.listing_id)}</strong> {change.state === "removed" ? "is no longer available"
        : "changed" + (change.changed_fields.length ? ": " + change.changed_fields.join(", ").replace(/_/g, " ") : "")}
    </li>)}</ul>}
    <div className="comparison-table-wrap" role="region" aria-label={name + " table"} tabIndex={0}>
      <table className="comparison-table"><caption className="visually-hidden">{name}. Cells marked Best have the best value in their row.</caption>
        <thead><tr><th scope="col">Attribute</th>{listings.map(item => <th scope="col" key={item.id}>
          <Link href={"/listings/" + item.id}><a>{comparisonTitle(item)}</a></Link></th>)}</tr></thead>
        <tbody>{rows.map(row => <tr key={row.key}>
          <th scope="row">{row.label}{row.formula && <small className="comparison-hint">{row.formula}</small>}{row.direction && <span className="comparison-hint">{row.direction === "lower" ? "Lower" : "Higher"} is better</span>}</th>
          {listings.map(item => {
            const cell = row.cells.find(entry => entry.listing_id === item.id);
            const known = cell?.known && cell.value != null;
            const best = known && cell.best;
            return <td key={item.id} className={best ? "comparison-best" : undefined}>
              {known ? formatListingValue(row.key, cell.value) : UNKNOWN}
              {best && <span className="comparison-best-label">Best</span>}
            </td>;
          })}</tr>)}</tbody>
      </table>
    </div>
    {notes.map((note, index) => <p className="muted" key={index}>{note}</p>)}
  </>;
  if (standalone) return <div className="saved-comparison">{body}</div>;
  return <div className="group-comparison">
    <details className="group-comparison-details">
      <summary><strong>{name}</strong> <span className="muted">· {listings.length} listings · saved by {comparison.saved_by.name}</span></summary>
      {body}
    </details>
  </div>;
}
