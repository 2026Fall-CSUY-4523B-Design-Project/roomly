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
    // detail is a string, a list of 422 field errors, or {code, message} when the client may branch on a reason.
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => `${item.loc.slice(1).join(".")}: ${item.msg}`).join(" ")
      : typeof detail === "string" ? detail
      : typeof detail?.message === "string" ? detail.message : "Something went wrong. Please try again.";
    const error = new Error(message);
    error.status = res.status;
    error.code = typeof detail === "object" && !Array.isArray(detail) ? detail?.code : undefined;
    throw error;
  }
  return res.status === 204 ? null : res.json();
}

export const getListing = (id) => accountRequest(`/listings/${encodeURIComponent(id)}`);

export const reportListing = (request, id, body) =>
  request(`/listings/${encodeURIComponent(id)}/reports`, { method: "POST", body });

// Email confirmation and password reset. The two "send" calls answer 202 whether or not the address
// has an account, so callers must show the same message either way.
export const signUp = (body) => accountRequest("/auth/sign-up", { method: "POST", body });
export const verifyEmail = (token) => accountRequest("/auth/verify-email", { method: "POST", body: { token } });
export const resendVerification = (email) =>
  accountRequest("/auth/verify-email/resend", { method: "POST", body: { email } });
export const forgotPassword = (email) => accountRequest("/auth/forgot-password", { method: "POST", body: { email } });
export const resetPassword = (token, password) =>
  accountRequest("/auth/reset-password", { method: "POST", body: { token, password } });

export const previewComparison = (listingIds) =>
  accountRequest("/comparisons/preview", { method: "POST", body: { listing_ids: listingIds } });
