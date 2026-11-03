export const UNKNOWN = "Unknown";

export const BOROUGHS = [
  { value: "manhattan", label: "Manhattan" },
  { value: "brooklyn", label: "Brooklyn" },
  { value: "queens", label: "Queens" },
  { value: "bronx", label: "Bronx" },
  { value: "staten_island", label: "Staten Island" },
];

export function boroughLabel(value) {
  return BOROUGHS.find((b) => b.value === value)?.label ?? UNKNOWN;
}

export function formatRent(cents) {
  if (cents === null || cents === undefined) return UNKNOWN;
  return `$${Math.round(cents / 100).toLocaleString("en-US")}/mo`;
}

export function formatBedrooms(n) {
  if (n === null || n === undefined) return UNKNOWN;
  return n === 0 ? "Studio" : `${n} bd`;
}

export function formatBathrooms(n) {
  if (n === null || n === undefined) return `${UNKNOWN} ba`;
  return `${n} ba`;
}

export function formatArea(sqft) {
  if (sqft === null || sqft === undefined) return `${UNKNOWN} sq ft`;
  return `${sqft.toLocaleString("en-US")} sq ft`;
}

export function formatDate(iso) {
  if (!iso) return UNKNOWN;
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatAmenity(key) {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
