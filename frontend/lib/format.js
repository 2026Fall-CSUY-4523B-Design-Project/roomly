// Display helpers. The API sends money as integer cents and an absent value as null, which
// the UI always shows as "Unknown" (SSDS: an unknown value is never guessed or shown as 0).

export const UNKNOWN = "Unknown";

export const BOROUGHS = [
  { value: "manhattan", label: "Manhattan" },
  { value: "brooklyn", label: "Brooklyn" },
  { value: "queens", label: "Queens" },
  { value: "bronx", label: "The Bronx" },
  { value: "staten_island", label: "Staten Island" },
];

const usd = (cents) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: cents % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  });

export function money(cents) {
  if (cents == null) return UNKNOWN;
  return usd(cents).format(cents / 100);
}

// "2,400" or "2400.50" typed by a person -> integer cents; blank -> null; nonsense -> NaN.
export function dollarsToCents(text) {
  const cleaned = String(text ?? "").replace(/[$,\s]/g, "");
  if (cleaned === "") return null;
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return NaN;
  return Math.round(Number(cleaned) * 100);
}

export function borough(value) {
  if (value == null) return UNKNOWN;
  return BOROUGHS.find((b) => b.value === value)?.label ?? value;
}

export function bedrooms(n) {
  if (n == null) return `${UNKNOWN} beds`;
  return n === 0 ? "Studio" : `${n} bed${n === 1 ? "" : "s"}`;
}

export function bathrooms(n) {
  if (n == null) return `${UNKNOWN} baths`;
  return `${n} bath${n === 1 ? "" : "s"}`;
}

export function area(sqft) {
  return sqft == null ? `${UNKNOWN} sq ft` : `${sqft.toLocaleString("en-US")} sq ft`;
}

// "2026-11-03" is a calendar date, not an instant: format it without a time-zone shift.
export function date(iso) {
  if (iso == null) return UNKNOWN;
  const day = /^\d{4}-\d{2}-\d{2}$/.test(iso);
  const d = day ? new Date(`${iso}T00:00:00Z`) : new Date(iso);
  if (Number.isNaN(d.getTime())) return UNKNOWN;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...(day ? { timeZone: "UTC" } : {}),
  });
}

export function plural(n, one, many = `${one}s`) {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
}
