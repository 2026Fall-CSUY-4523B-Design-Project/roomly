async function get(path, params) {
  const qs = params ? `?${params}` : "";
  const res = await fetch(`/api${path}${qs}`);
  if (!res.ok) throw new Error(`GET ${path} failed with ${res.status}`);
  return res.json();
}

export function searchListings(filters = {}, { sort = "newest", limit = 20, offset = 0 } = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v));
    else params.set(key, value);
  }
  params.set("sort", sort);
  params.set("limit", limit);
  params.set("offset", offset);
  return get("/search", params);
}
