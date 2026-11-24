import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useRef, useState } from "react";

import { MAX_COMPARISON_LISTINGS, useComparison } from "@/lib/comparison";

const UNDO_MS = 6000;

// Fixed bottom bar; the page reserves its height via --comparison-bar-height so no content is hidden.
export default function ComparisonSelection() {
  const { selected, ready, remove, clear, restore } = useComparison();
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [cleared, setCleared] = useState(null);
  const bar = useRef(null);
  const onComparePage = router.pathname === "/compare";
  const visible = ready && !onComparePage && (selected.length > 0 || cleared);

  useEffect(() => {
    if (!cleared) return;
    const timer = setTimeout(() => setCleared(null), UNDO_MS);
    return () => clearTimeout(timer);
  }, [cleared]);

  useEffect(() => {
    if (selected.length && cleared) setCleared(null);
  }, [selected.length, cleared]);

  useEffect(() => {
    const root = document.documentElement;
    const node = bar.current;
    if (!visible || !node) return;
    const update = () => root.style.setProperty("--comparison-bar-height", `${node.offsetHeight}px`);
    update();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(node);
    return () => { observer?.disconnect(); root.style.removeProperty("--comparison-bar-height"); };
  }, [visible]);

  if (!visible) return null;

  if (!selected.length) {
    return <section ref={bar} className="comparison-selection" aria-label="Comparison selection">
      <div className="comparison-selection-heading">
        <span role="status">Selection cleared.</span>
        <button type="button" className="button secondary" onClick={() => { restore(cleared); setCleared(null); }}>Undo</button>
      </div>
    </section>;
  }

  const canCompare = selected.length >= 2;
  const hint = !canCompare ? "Select at least 2 listings to compare."
    : selected.length >= MAX_COMPARISON_LISTINGS ? "Limit reached. Remove one to add another." : null;

  return <section ref={bar} className={`comparison-selection${expanded ? " expanded" : ""}`} aria-label="Comparison selection">
    <div className="comparison-selection-heading">
      <div className="comparison-selection-count">
        <strong role="status">{selected.length} of {MAX_COMPARISON_LISTINGS} listings selected</strong>
        {hint && <span id="comparison-hint" className="comparison-selection-hint">{hint}</span>}
      </div>
      <button type="button" className="button secondary comparison-selection-toggle" aria-expanded={expanded}
        aria-controls="comparison-selection-list" onClick={() => setExpanded((value) => !value)}>
        {expanded ? "Hide" : "Show"} listings
      </button>
      {canCompare ? (
        <Link href="/compare"><a className="button">Compare listings</a></Link>
      ) : (
        <button type="button" className="button" disabled aria-describedby="comparison-hint">Compare listings</button>
      )}
      <button type="button" className="button secondary" onClick={() => { setCleared(selected); clear(); }}>Clear</button>
    </div>
    <ul id="comparison-selection-list">{selected.map((item) => <li key={item.id}>
      <Link href={`/listings/${item.id}`}><a>{item.title}</a></Link>
      <button type="button" className="comparison-chip-remove" aria-label={`Remove ${item.title} from comparison`}
        onClick={() => remove(item.id)}>×</button>
    </li>)}</ul>
  </section>;
}
