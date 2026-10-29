// Fetch client for the Roomly API. Every call goes to same-origin /api/*, which next.config.js
// rewrites to the backend, so the browser never needs CORS or the backend's address.
//
// Errors arrive as { detail }: a string for service errors (401/403/404/409/503) or, for 422,
// a list of { loc, msg, type } like FastAPI's. ApiError keeps both shapes and maps 422 items to
// fields ({ email: "..." }) so forms can show the message next to the input.

import { clearSession, loadSession } from "./auth.js";

const PREFIX = "/api";

export class ApiError extends Error {
  constructor(status, detail) {
    const items = Array.isArray(detail) ? detail : [];
    const message =
      typeof detail === "string" ? detail : items[0]?.msg ?? (status ? `Request failed (${status})` : "Network error");
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.fields = {};
    for (const item of items) {
      const field = item.loc?.[item.loc.length - 1];
      if (typeof field === "string" && !(field in this.fields)) this.fields[field] = item.msg;
    }
  }
}

// { borough: ["queens", "bronx"], max_rent_cents: 300000, sort: "" } -> "?borough=queens&borough=bronx&max_rent_cents=300000"
// Values are percent-encoded: a raw "+" in a timestamp would otherwise arrive as a space.
export function query(params = {}) {
  const parts = [];
  for (const [key, value] of Object.entries(params)) {
    for (const v of Array.isArray(value) ? value : [value]) {
      if (v === null || v === undefined || v === "" || v === false) continue;
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(v))}`);
    }
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

export async function request(method, path, { body, params, token = loadSession()?.token } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${PREFIX}${path}${query(params)}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    console.error(`[roomly] ${method} ${path} failed to reach the server`, err);
    throw new ApiError(0, "Can't reach Roomly right now. Check your connection and try again.");
  }

  const text = res.status === 204 ? "" : await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    if (res.status === 401 && token) clearSession(); // expired or revoked: sign the tab out
    // 422 items echo the submitted input (passwords included), so only string details are logged
    console.warn(`[roomly] ${method} ${path} -> ${res.status}`, typeof data?.detail === "string" ? data.detail : "");
    throw new ApiError(res.status, data?.detail ?? null);
  }
  return data;
}

const get = (path, params) => request("GET", path, { params });
const post = (path, body) => request("POST", path, { body });

// The calls the pages make today. Everything else is request(method, path, ...) away; see
// docs/backend.md for the endpoint map.
export const api = {
  signUp: (body) => post("/auth/sign-up", body),
  signIn: (body) => post("/auth/sign-in", body),
  signOut: () => post("/auth/sign-out"),
  me: () => get("/me"),

  search: (criteria) => get("/search", criteria),
  listing: (id) => get(`/listings/${encodeURIComponent(id)}`),

  groups: () => get("/groups"),
  group: (id) => get(`/groups/${encodeURIComponent(id)}`),
  createGroup: (name) => post("/groups", { name }),
  invite: (groupId, email) => post(`/groups/${encodeURIComponent(groupId)}/invitations`, { email }),
  sentInvitations: (groupId) => get(`/groups/${encodeURIComponent(groupId)}/invitations`),
  leaveGroup: (groupId) => post(`/groups/${encodeURIComponent(groupId)}/leave`),
  transferOwnership: (groupId, userId) =>
    post(`/groups/${encodeURIComponent(groupId)}/transfer`, { user_id: userId }),
  removeMember: (groupId, userId) =>
    request("DELETE", `/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(userId)}`),
  invitations: () => get("/invitations"),
  acceptInvitation: (id) => post(`/invitations/${encodeURIComponent(id)}/accept`),
  declineInvitation: (id) => post(`/invitations/${encodeURIComponent(id)}/decline`),
};
