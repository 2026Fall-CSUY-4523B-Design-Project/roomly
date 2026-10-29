import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import { MemoryStorage, inOneHour, installStorage } from "./storage.mjs";

installStorage(new MemoryStorage());
const { ApiError, api, query, request } = await import("../lib/api.js");
const { loadSession, saveSession } = await import("../lib/auth.js");

const realFetch = globalThis.fetch;
let calls;

function respond(status, body) {
  calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };
}

beforeEach(() => installStorage(new MemoryStorage()));
afterEach(() => {
  globalThis.fetch = realFetch;
});

test("query repeats lists, drops empty filters, keeps zero, and percent-encodes", () => {
  assert.equal(
    query({ borough: ["queens", "bronx"], max_rent_cents: null, min_bedrooms: 0, no_broker_fee: false, q: "" }),
    "?borough=queens&borough=bronx&min_bedrooms=0",
  );
  assert.equal(query({ before: "2026-10-29T12:00:00+00:00" }), "?before=2026-10-29T12%3A00%3A00%2B00%3A00");
  assert.equal(query({}), "");
});

test("calls go to same-origin /api with JSON and the bearer token", async () => {
  saveSession({ token: "tok", expires_at: inOneHour(), user: { id: "u" } });
  respond(201, { id: "g1", name: "Crew" });
  const group = await api.createGroup("Crew");
  assert.equal(group.id, "g1");
  const [{ url, init }] = calls;
  assert.equal(url, "/api/groups");
  assert.equal(init.method, "POST");
  assert.equal(init.headers.Authorization, "Bearer tok");
  assert.equal(init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(init.body), { name: "Crew" });
});

test("guests send no Authorization header and GETs send no body", async () => {
  respond(200, { items: [], total: 0, limit: 20, offset: 0 });
  await api.search({ borough: ["queens"], sort: "newest" });
  assert.equal(calls[0].url, "/api/search?borough=queens&sort=newest");
  assert.equal(calls[0].init.headers.Authorization, undefined);
  assert.equal(calls[0].init.body, undefined);
});

test("422 detail lists map onto form fields", async () => {
  respond(422, { detail: [{ loc: ["body", "email"], msg: "not a valid email address", type: "pattern" }] });
  const err = await api.signUp({ email: "x", password: "longenough" }).catch((e) => e);
  assert.ok(err instanceof ApiError);
  assert.equal(err.status, 422);
  assert.equal(err.fields.email, "not a valid email address");
  assert.equal(err.message, "not a valid email address");
});

test("a 401 on an authenticated call signs the tab out", async () => {
  saveSession({ token: "stale", expires_at: inOneHour(), user: { id: "u" } });
  respond(401, { detail: "session expired, sign in again" });
  const err = await api.groups().catch((e) => e);
  assert.equal(err.status, 401);
  assert.equal(err.message, "session expired, sign in again");
  assert.equal(loadSession(), null);
});

test("204 resolves to null; an unreachable server is a friendly error", async () => {
  respond(204);
  assert.equal(await request("POST", "/groups/g1/leave"), null);
  globalThis.fetch = async () => {
    throw new TypeError("fetch failed");
  };
  const err = await api.me().catch((e) => e);
  assert.equal(err.status, 0);
  assert.match(err.message, /Can't reach Roomly/);
});
