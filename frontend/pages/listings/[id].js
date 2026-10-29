import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";

import SprintNotice from "@/components/SprintNotice";
import { api } from "@/lib/api";
import { UNKNOWN, area, bathrooms, bedrooms, borough, date, money } from "@/lib/format";

import styles from "@/styles/listing.module.css";

const FIELD_LABELS = {
  advertised_rent_cents: "Advertised rent",
  net_effective_rent_cents: "Net effective rent",
  broker_fee_cents: "Broker fee",
  monthly_fees_cents: "Monthly fees",
  bedrooms: "Bedrooms",
  bathrooms: "Bathrooms",
  area_sqft: "Area",
  move_in_date: "Move-in date",
  lease_term_months: "Lease term",
  min_lease_days: "Minimum stay",
};

const AVAILABILITY = {
  available: { label: "Available", badge: "badge-good" },
  unavailable: { label: "No longer available", badge: "badge-warn" },
  unknown: { label: "Availability unknown", badge: "" },
};

// The listing card (R-2.2): every value with where it came from and when it was collected.
export default function ListingPage() {
  const router = useRouter();
  const { id } = router.query;
  const [state, setState] = useState({ card: null, error: null });

  useEffect(() => {
    if (!id) return;
    api.listing(id).then(
      (card) => setState({ card, error: null }),
      (error) => setState({ card: null, error }),
    );
  }, [id]);

  if (state.error) {
    return (
      <div className="container page">
        <div className="empty">
          <h3>{state.error.status === 404 ? "Listing not found" : "Couldn't load this listing"}</h3>
          <p>{state.error.status === 404 ? "It may have been merged into another listing or removed." : state.error.message}</p>
          <Link href="/">
            <a className="btn btn-ghost">Back to search</a>
          </Link>
        </div>
      </div>
    );
  }
  const card = state.card;
  if (!card) {
    return (
      <div className="container page">
        <div className="skeleton" style={{ minHeight: 360 }} />
      </div>
    );
  }
  if (card.merged_into_id) {
    return (
      <div className="container page">
        <div className="empty">
          <h3>This listing was merged</h3>
          <p>An administrator found it was the same apartment as another listing.</p>
          <Link href={`/listings/${card.merged_into_id}`}>
            <a className="btn btn-primary">Open the merged listing</a>
          </Link>
        </div>
      </div>
    );
  }

  const availability = AVAILABILITY[card.availability] ?? AVAILABILITY.unknown;
  const conflicts = Object.entries(card.conflicts ?? {});
  const ppsf = card.price_per_sqft_cents;

  return (
    <div className="container page">
      <Head>
        <title>{card.title || card.address_line || "Listing"} · Roomly</title>
      </Head>
      <Link href="/">
        <a className="btn btn-quiet" style={{ marginLeft: -10 }}>
          ← Search
        </a>
      </Link>

      <header className={styles.header}>
        <div>
          <p className="eyebrow">
            {borough(card.borough)}
            {card.postal_code ? ` · ${card.postal_code}` : ""}
          </p>
          <h1>{card.title || card.address_line || "Untitled listing"}</h1>
          {card.address_line ? (
            <p className="lede" style={{ marginBottom: 12 }}>
              {card.address_line}
              {card.unit ? `, ${card.unit}` : ""}
            </p>
          ) : null}
          <div className="row" style={{ gap: 8 }}>
            <span className={`badge ${availability.badge}`}>{availability.label}</span>
            {card.is_synthetic ? <span className="badge">Sample data, not a real apartment</span> : null}
            {conflicts.length ? <span className="badge badge-warn">Sources disagree</span> : null}
          </div>
        </div>
        <div className={styles.price}>
          <div className={styles.rent}>
            {card.advertised_rent_cents == null ? (
              <span className="unknown">{UNKNOWN}</span>
            ) : (
              <>
                {money(card.advertised_rent_cents)}
                <span className={styles.per}>/mo</span>
              </>
            )}
          </div>
          <div className="hint">advertised rent</div>
        </div>
      </header>

      <div className="split">
        <div className="stack">
          <section className="card">
            <h3>The details</h3>
            <dl className={styles.facts}>
              <Fact label="Bedrooms" value={card.bedrooms} show={bedrooms} />
              <Fact label="Bathrooms" value={card.bathrooms} show={bathrooms} />
              <Fact label="Area" value={card.area_sqft} show={area} />
              <Fact label="Move-in" value={card.move_in_date} show={date} />
              <Fact label="Net effective rent" value={card.net_effective_rent_cents} show={money} />
              <Fact label="Broker fee" value={card.broker_fee_cents} show={money} />
              <Fact label="Monthly fees" value={card.monthly_fees_cents} show={money} />
              <Fact label="Lease term" value={card.lease_term_months} show={(m) => `${m} months`} />
              <Fact label="Minimum stay" value={card.min_lease_days} show={(d) => `${d} days`} />
              <div className={styles.fact}>
                <dt>Price per sq ft</dt>
                <dd className={ppsf.value == null ? "unknown" : undefined} title={ppsf.formula}>
                  {money(ppsf.value)}
                  <span className={styles.formula}>{ppsf.formula}</span>
                </dd>
              </div>
            </dl>
          </section>

          {conflicts.length ? (
            <section className="card">
              <h3>Where sources disagree</h3>
              <p className="muted">Roomly shows these as reported instead of picking one silently.</p>
              <ul className={styles.list}>
                {conflicts.map(([field, values]) => (
                  <li key={field}>
                    <strong>{FIELD_LABELS[field] ?? field}</strong>:{" "}
                    {values.map((v) => (v.value == null ? UNKNOWN : String(v.value))).join(" vs ")}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="card">
            <h3>Amenities</h3>
            {card.amenities.length ? (
              <div className="row" style={{ gap: 8 }}>
                {card.amenities.map((a) => (
                  <span key={a} className="badge">
                    {a.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            ) : (
              <p className="unknown" style={{ margin: 0 }}>
                None listed. That means unknown, not &ldquo;none&rdquo;.
              </p>
            )}
          </section>
        </div>

        <aside className="stack">
          <section className="card">
            <h3>Sources</h3>
            <ul className={styles.list}>
              {card.sources.map((s) => (
                <li key={`${s.source_name}-${s.external_id}`}>
                  <div style={{ fontWeight: 600 }}>
                    {s.source_name}
                    {s.is_synthetic ? <span className="badge" style={{ marginLeft: 6 }}>synthetic</span> : null}
                  </div>
                  <div className="hint">
                    Collected {date(s.collected_at)}
                    {s.original_url ? (
                      <>
                        {" · "}
                        <a href={s.original_url} target="_blank" rel="noopener noreferrer nofollow">
                          original post
                        </a>
                      </>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
            <p className="hint" style={{ margin: "12px 0 0" }}>
              Last updated {date(card.updated_at)} · first seen {date(card.created_at)}
            </p>
          </section>

          {card.price_history.length > 1 ? (
            <section className="card">
              <h3>Price history</h3>
              <ul className={styles.list}>
                {card.price_history.map((p) => (
                  <li key={p.observed_at} className="row" style={{ justifyContent: "space-between" }}>
                    <span>{date(p.observed_at)}</span>
                    <strong>{money(p.rent_cents)}</strong>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <SprintNotice
            sprint={4}
            compact
            title="Commute, compare and report"
            items={[
              "Travel time to your saved destinations",
              "Add to a comparison or share it with your group",
              "Report a wrong value or a wrong merge from this card",
            ]}
            endpoints={["POST /comparisons/preview", "POST /listings/{id}/reports"]}
          />
        </aside>
      </div>
    </div>
  );
}

function Fact({ label, value, show }) {
  return (
    <div className={styles.fact}>
      <dt>{label}</dt>
      <dd className={value == null ? "unknown" : undefined}>{value == null ? UNKNOWN : show(value)}</dd>
    </div>
  );
}
