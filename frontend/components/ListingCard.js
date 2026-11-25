import Link from "next/link";
import CompareButton from "@/components/CompareButton";

import {
  boroughLabel,
  formatAmenity,
  formatArea,
  formatBathrooms,
  formatBedrooms,
  formatDate,
  formatRent,
} from "@/lib/format";

// One search result (ListingSummaryDTO). Unknown values are labeled, synthetic data and source conflicts are flagged.
export default function ListingCard({ listing }) {
  const title = listing.title || listing.address_line || "Untitled listing";
  const address = [listing.address_line, listing.unit && `Unit ${listing.unit}`].filter(Boolean).join(", ");

  return (
    <article className="card listing-card">
      <div className="card-top">
        <span className="rent">{formatRent(listing.advertised_rent_cents)}</span>
        <span className="tags">
          {listing.is_synthetic && <span className="tag">Synthetic</span>}
          {listing.has_conflicts && <span className="tag warn" title="Sources disagree on a value">Conflicting sources</span>}
        </span>
      </div>

      <h3 className="card-title">
        {/* The title link stretches over the whole card, so anywhere on it opens the listing. */}
        <Link href={`/listings/${listing.id}`}>
          <a className="listing-card-link">{title}</a>
        </Link>
      </h3>
      <p className="muted">
        {address} · {boroughLabel(listing.borough)}
      </p>

      <p className="facts">
        {formatBedrooms(listing.bedrooms)} · {formatBathrooms(listing.bathrooms)} · {formatArea(listing.area_sqft)}
      </p>
      <p className="muted">Move-in: {formatDate(listing.move_in_date)}</p>

      {listing.amenities.length > 0 && (
        <ul className="amenities">
          {listing.amenities.map((a) => (
            <li key={a}>{formatAmenity(a)}</li>
          ))}
        </ul>
      )}
      <div className="listing-card-footer">
        <CompareButton listing={listing} />
        <span className="listing-card-cta" aria-hidden="true">View details →</span>
      </div>
    </article>
  );
}
