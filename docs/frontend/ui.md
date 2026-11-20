# UI, styles and formatting

## One stylesheet

`styles/globals.css` (≈270 lines) is the entire styling layer: no CSS modules, no Tailwind, no
component-scoped styles. It is imported once in `_app.js` and organised as: tokens → base elements →
header → dashboard → filters → results → auth panel.

Design tokens are CSS custom properties on `:root` — `--bg`, `--surface`, `--text`, `--muted`,
`--border`, `--accent`, `--warn-bg`, `--warn-text`, `--error`, `--radius`. Use them instead of
literals; a new colour means a new token.

Reusable classes:

| Class | Use |
| --- | --- |
| `.button`, `.button.secondary` | primary / outline action, on `<button>` or `<a>` |
| `.card` | bordered surface (listing cards, auth panel) |
| `.grid` | auto-fill result grid, min 260px columns |
| `.muted`, `.error` | secondary text / validation and failure text |
| `.tag`, `.tag.warn` | small pills: "Synthetic", "Conflicting sources" |
| `.row`, `.check` | horizontal field group / checkbox with label |
| `.dashboard`, `.filters`, `.results-bar`, `.auth-panel`, `.auth-form` | page-level layout |

Breakpoints: 720px turns `.dashboard` from a 240px sidebar + results into one column; 480px trims
the auth panel margins. Layout is grid/flex only — no positioning hacks, no images, no icon font.

## `lib/format.js`

The single place that turns API values into display strings. Every helper tolerates `null` /
`undefined` and returns a labelled fallback rather than hiding the value, because the SSDS requires
unknown data to be visible:

| Helper | Output |
| --- | --- |
| `formatRent(cents)` | `$2,400/mo` — divides by 100, `Unknown` when absent |
| `formatBedrooms(n)` | `Studio` (0), `3 bd` |
| `formatBathrooms(n)` | `1.5 ba` |
| `formatArea(sqft)` | `650 sq ft` |
| `formatDate(iso)` | `Sep 1, 2026`; parsed as a local date, not `new Date(iso)` (avoids the UTC off-by-one) |
| `boroughLabel(value)` | display name for the enum, else `Unknown` |
| `formatAmenity(key)` | `no_broker_fee` → `No broker fee` |

Rents are integer cents end to end. Dollars exist only inside `FilterPanel` (the `<input
type="number">` the user types in) and inside `formatRent` at render time.

## Accessibility conventions

The existing components already carry these; match them rather than adding a library:

- Every input is inside a `<label>` (or has `aria-label` when a visible label would repeat a
  heading), and every `<fieldset>` has a `<legend>`.
- Async state uses `role="status"` (loading) and `role="alert"` (errors), so screen readers announce
  it without focus changes.
- `:focus-visible` gets a 2px `--accent` outline globally; don't remove outlines.
- Landmarks: `<header>`, `<nav aria-label="Main">`, `<main>`, `<section aria-labelledby>` on the
  results region.
- Buttons disable while pending and change their label ("Please wait…", "Signing out…") instead of
  showing a spinner.

## Adding UI

Copy the closest existing pattern: a page composes `Header` + `<main>`; a card is `<article
class="card">`; formatting goes through `lib/format.js`; data comes from `lib/api.js`. If a new
class is needed, add it to `globals.css` in the matching section and build it from tokens.
