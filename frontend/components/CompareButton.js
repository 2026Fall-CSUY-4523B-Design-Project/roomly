import Link from "next/link";

import { MAX_COMPARISON_LISTINGS, comparisonTitle, useComparison } from "@/lib/comparison";

// showCompareLink: offer a shortcut to /compare once this listing is part of a comparable selection.
export default function CompareButton({ listing, showCompareLink = false }) {
  const { selected, ready, toggle } = useComparison();
  const active = selected.some((item) => item.id === listing.id);
  const full = !active && selected.length >= MAX_COMPARISON_LISTINGS;
  return <div className="compare-control">
    <button type="button" className={`button compare-button${active ? " active" : " secondary"}`}
      aria-pressed={active} disabled={!ready || full} onClick={() => toggle(listing)}
      aria-label={`Compare ${comparisonTitle(listing)}`}
      title={full ? `You can compare up to ${MAX_COMPARISON_LISTINGS} listings. Remove one to add this.` : undefined}>
      {active ? "✓ Comparing" : full ? "Comparison full" : "Compare"}
    </button>
    {showCompareLink && active && selected.length >= 2 && (
      <Link href="/compare"><a className="compare-now">Compare now ({selected.length})</a></Link>
    )}
  </div>;
}
