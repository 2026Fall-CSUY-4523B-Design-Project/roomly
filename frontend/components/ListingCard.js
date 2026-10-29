import Link from "next/link";

import { area, bathrooms, bedrooms, borough, date, money } from "@/lib/format";

import styles from "./ListingCard.module.css";

// One search result (ListingSummaryDTO). Unknown values are labeled, never hidden or zeroed.
export default function ListingCard({ listing }) {
  const rentKnown = listing.advertised_rent_cents != null;
  const net = listing.net_effective_rent_cents;
  return (
    <Link href={`/listings/${listing.id}`}>
      <a className={`card card-link ${styles.card}`}>
        <div className={styles.top}>
          <span className={styles.borough}>{borough(listing.borough)}</span>
          <span className="row" style={{ gap: 6 }}>
            {listing.is_synthetic ? <span className="badge">Sample data</span> : null}
            {listing.has_conflicts ? <span className="badge badge-warn">Sources disagree</span> : null}
          </span>
        </div>
        <div className={styles.rent}>
          <span className={rentKnown ? undefined : "unknown"}>{money(listing.advertised_rent_cents)}</span>
          {rentKnown ? <span className={styles.per}>/mo</span> : null}
        </div>
        {net != null && net !== listing.advertised_rent_cents ? (
          <div className={styles.net}>{money(net)} net effective</div>
        ) : null}
        <div className={styles.title}>{listing.title || listing.address_line || "Untitled listing"}</div>
        {listing.title && listing.address_line ? (
          <div className={styles.address}>
            {listing.address_line}
            {listing.unit ? `, ${listing.unit}` : ""}
          </div>
        ) : null}
        <ul className={styles.facts}>
          <Fact known={listing.bedrooms != null}>{bedrooms(listing.bedrooms)}</Fact>
          <Fact known={listing.bathrooms != null}>{bathrooms(listing.bathrooms)}</Fact>
          <Fact known={listing.area_sqft != null}>{area(listing.area_sqft)}</Fact>
        </ul>
        <div className={styles.foot}>
          <span className={listing.move_in_date ? undefined : "unknown"}>
            Move-in {listing.move_in_date ? date(listing.move_in_date) : "Unknown"}
          </span>
          <span className={styles.updated}>Updated {date(listing.updated_at)}</span>
        </div>
      </a>
    </Link>
  );
}

function Fact({ known, children }) {
  return <li className={known ? undefined : "unknown"}>{children}</li>;
}
