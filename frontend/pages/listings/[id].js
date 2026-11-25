import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";

import CompareButton from "@/components/CompareButton";
import GroupPicker from "@/components/GroupPicker";
import Header from "@/components/Header";
import ListingReport from "@/components/ListingReport";
import { getListing } from "@/lib/api";
import {
  UNKNOWN, boroughLabel, formatAmenity, formatArea, formatBathrooms, formatBedrooms,
  formatDate, formatListingValue, formatMoney, formatTimestamp,
} from "@/lib/format";

function SourceLink({ url }) {
  // Source URLs are external data; only HTTP(S) links may be opened.
  let safe = false;
  try { safe = ["http:", "https:"].includes(new URL(url).protocol); } catch {}
  return safe ? <a href={url} target="_blank" rel="noopener noreferrer">View original listing</a> : <span className="muted">Original link unavailable</span>;
}

function Facts({ items }) {
  return <dl className="listing-facts">{items.map(([label, value]) => (
    <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
  ))}</dl>;
}

// R-2.2: preserve Unknown values, source provenance and disagreements on the full listing card.
export default function ListingDetail() {
  const router = useRouter();
  const id = typeof router.query.id === "string" ? router.query.id : null;
  const [result, setResult] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!router.isReady || !id) return;
    let cancelled = false;
    setResult(null);
    getListing(id).then((listing) => {
      if (!cancelled) setResult({ id, listing });
    }).catch((error) => {
      if (!cancelled) setResult({ id, error });
    });
    return () => { cancelled = true; };
  }, [router.isReady, id, attempt]);

  const current = result?.id === id ? result : null;
  const listing = current?.listing;
  const missing = [404, 422].includes(current?.error?.status);
  const title = listing?.title || listing?.address_line || "Listing details";

  return (
    <>
      <Head><title>{title} · Roomly</title></Head>
      <Header />
      <main className="listing-detail">
        <Link href="/"><a>← Back to listings</a></Link>
        {!current && <p role="status">Loading listing…</p>}
        {current?.error && <section className="card">
          <h1>{missing ? "Listing not found" : "Could not load listing"}</h1>
          <p role="alert">{missing ? "This listing does not exist. Return to search to find another place." : "Please try again in a moment."}</p>
          {!missing && <button className="button" onClick={() => setAttempt((n) => n + 1)}>Try again</button>}
        </section>}
        {listing && <>
          <section className="card">
            <div className="card-top">
              <span className="rent">{listing.advertised_rent_cents == null ? UNKNOWN : `${formatMoney(listing.advertised_rent_cents)}/mo`}</span>
              <div className="tags">
                {listing.is_synthetic && <span className="tag">Synthetic</span>}
                {listing.has_conflicts && <span className="tag warn">Conflicting sources</span>}
                <span className="tag">{formatAmenity(listing.availability)}</span>
              </div>
            </div>
            <h1>{title}</h1>
            <CompareButton listing={listing} showCompareLink />
            <div className="listing-group-share">
              <GroupPicker label="Discuss with a group" confirmLabel="Open discussion" skipIfSingle
                onConfirm={async (request, groupId) => ({ pathname: "/groups/[id]", query: { id: groupId, listing: listing.id } })} />
            </div>
            <p>{[listing.address_line, listing.unit && `Unit ${listing.unit}`, boroughLabel(listing.borough), listing.postal_code].filter(Boolean).join(", ")}</p>
            <p>{formatBedrooms(listing.bedrooms)} · {formatBathrooms(listing.bathrooms)} · {formatArea(listing.area_sqft)}</p>
            <p className="muted">Updated {formatTimestamp(listing.updated_at)}</p>
            {listing.status !== "searchable" && <p className="listing-notice">Listing status: {formatAmenity(listing.status)}.</p>}
            {listing.merged_into_id && <p>This listing was merged. <Link href={`/listings/${listing.merged_into_id}`}><a>View the combined listing</a></Link>.</p>}
          </section>
          <section className="card" aria-labelledby="cost-heading">
            <h2 id="cost-heading">Costs and lease</h2>
            <Facts items={[
              ["Advertised monthly rent", formatMoney(listing.advertised_rent_cents)],
              ["Net-effective monthly rent", formatMoney(listing.net_effective_rent_cents)],
              ["Lease term", listing.lease_term_months == null ? UNKNOWN : `${listing.lease_term_months} months`],
              ["Broker fee", formatMoney(listing.broker_fee_cents)],
              ["Monthly fees", formatMoney(listing.monthly_fees_cents)],
              ["Minimum lease", listing.min_lease_days == null ? UNKNOWN : `${listing.min_lease_days} days`],
              ["Move-in date", formatDate(listing.move_in_date)],
              ["Monthly rent per sq ft", formatMoney(listing.price_per_sqft_cents.value)],
            ]} />
          </section>
          <section className="card" aria-labelledby="amenities-heading">
            <h2 id="amenities-heading">Amenities</h2>
            {listing.amenities.length ? <ul className="amenities">{listing.amenities.map((amenity) => <li key={amenity}>{formatAmenity(amenity)}</li>)}</ul> : <p className="muted">No amenities listed.</p>}
          </section>
          <section className="card" aria-labelledby="sources-heading">
            <h2 id="sources-heading">Sources</h2>
            {listing.sources.length ? <ul className="listing-sources">{listing.sources.map((source, index) => (
              <li key={`${source.source_name}-${source.external_id}-${index}`}>
                <strong>{source.source_name}</strong> · {formatAmenity(source.source_kind)} {source.is_synthetic && <span className="tag">Synthetic</span>}
                <p className="muted">Collected {formatTimestamp(source.collected_at)}</p>
                <SourceLink url={source.original_url} />
              </li>
            ))}</ul> : <p className="muted">No sources recorded.</p>}
          </section>
          <section className="card" aria-labelledby="conflicts-heading">
            <h2 id="conflicts-heading">Conflicting information</h2>
            {Object.keys(listing.conflicts).length ? <>
              <p>Sources disagree on these values. Confirm the details with the original sources.</p>
              <Facts items={Object.entries(listing.conflicts).map(([field, rows]) => [
                formatAmenity(field.replace(/_cents$/, "")),
                rows.map((row) => formatListingValue(field, row.value)).join(" / "),
              ])} />
            </> : <p className="muted">No source conflicts recorded.</p>}
          </section>
          <section className="card" aria-labelledby="history-heading">
            <h2 id="history-heading">Price history</h2>
            {listing.price_history.length ? <div className="listing-table-wrap"><table className="listing-table">
              <caption className="muted">Observed advertised monthly rent</caption>
              <thead><tr><th scope="col">Observed</th><th scope="col">Monthly rent</th></tr></thead>
              <tbody>{listing.price_history.map((point, index) => <tr key={`${point.observed_at}-${index}`}>
                <td>{formatTimestamp(point.observed_at)}</td><td>{formatMoney(point.rent_cents)}</td>
              </tr>)}</tbody>
            </table></div> : <p className="muted">No price history recorded.</p>}
          </section>
          <ListingReport key={`${listing.id}`} listingId={listing.id} />
        </>}
      </main>
    </>
  );
}
