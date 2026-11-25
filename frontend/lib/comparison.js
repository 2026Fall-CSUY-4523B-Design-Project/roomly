import { createContext, useContext, useEffect, useState } from "react";

const ComparisonContext = createContext(null);
const STORAGE_KEY = "roomly.comparison";
export const MAX_COMPARISON_LISTINGS = 4;

export const comparisonTitle = (listing) => listing.title || listing.address_line || "Untitled listing";

// A guest's selection belongs to this tab, independent of account sessions.
export function ComparisonProvider({ children }) {
  const [selected, setSelected] = useState([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "[]");
      const seen = new Set();
      if (Array.isArray(saved)) setSelected(saved.filter((item) => {
        if (!item || typeof item.id !== "string" || typeof item.title !== "string" || seen.has(item.id)) return false;
        seen.add(item.id);
        return true;
      }).slice(0, MAX_COMPARISON_LISTINGS));
    } catch { /* Storage can be unavailable; selection still works in memory. */ }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(selected)); } catch {}
  }, [selected, ready]);

  function toggle(listing) {
    setSelected((previous) => {
      if (previous.some((item) => item.id === listing.id)) return previous.filter((item) => item.id !== listing.id);
      if (previous.length >= MAX_COMPARISON_LISTINGS) return previous;
      return [...previous, { id: listing.id, title: comparisonTitle(listing) }];
    });
  }

  return <ComparisonContext.Provider value={{ selected, ready, toggle,
    remove: (id) => setSelected((previous) => previous.filter((item) => item.id !== id)),
    clear: () => setSelected([]),
    // Load a saved comparison back into the selection, replacing whatever was there.
    replace: (items) => setSelected(items.slice(0, MAX_COMPARISON_LISTINGS)),
    // Undo for clear: only restores into an empty selection, so it never exceeds the limit.
    restore: (items) => setSelected((previous) => previous.length ? previous : items.slice(0, MAX_COMPARISON_LISTINGS)),
  }}>{children}</ComparisonContext.Provider>;
}

export const useComparison = () => useContext(ComparisonContext);

// R-4: best/known flags come from the API; supplementary summary fields have no ranking.
const SUMMARY_ROWS = [["bathrooms", "Bathrooms"], ["amenities", "Amenities"], ["availability", "Availability"]];

export function comparisonRows(table) {
  return [...table.rows, ...SUMMARY_ROWS.map(([key, label]) => ({ key, label, cells: table.listings.map((listing) => ({
    listing_id: listing.id, known: listing[key] != null, value: listing[key], best: false,
  })) }))];
}
