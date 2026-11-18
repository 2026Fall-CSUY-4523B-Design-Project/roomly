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

export async function accountRequest(path, { method = "GET", body, token } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const message = Array.isArray(data.detail)
      ? data.detail.map((item) => `${item.loc.slice(1).join(".")}: ${item.msg}`).join(" ")
      : typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
    const error = new Error(message);
    error.status = res.status;
    throw error;
  }
  return res.status === 204 ? null : res.json();
}
