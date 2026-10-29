import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { MemoryStorage, inOneHour, installStorage } from "./storage.mjs";

let storage = installStorage(new MemoryStorage());
const { clearSession, loadSession, onSessionChange, safeNext, saveSession } = await import("../lib/auth.js");

const session = (expires_at = inOneHour()) => ({ token: "t-1", expires_at, user: { id: "u-1", role: "user" } });

beforeEach(() => {
  storage = installStorage(new MemoryStorage());
});

test("a saved session survives a reload and clears on sign-out", () => {
  saveSession(session());
  assert.equal(loadSession().token, "t-1");
  assert.match(storage.getItem("roomly.session"), /t-1/);
  clearSession();
  assert.equal(loadSession(), null);
  assert.equal(storage.getItem("roomly.session"), null);
});

test("an expired or malformed session reads as signed out and is dropped", () => {
  storage.setItem("roomly.session", JSON.stringify(session("2020-01-01T00:00:00Z")));
  assert.equal(loadSession(), null);
  assert.equal(storage.getItem("roomly.session"), null);
  storage.setItem("roomly.session", "{not json");
  assert.equal(loadSession(), null);
});

test("listeners hear sign-in and sign-out", () => {
  const seen = [];
  const stop = onSessionChange((s) => seen.push(s?.token ?? null));
  saveSession(session());
  clearSession();
  stop();
  saveSession(session());
  assert.deepEqual(seen, ["t-1", null]);
});

test("without working storage the session lives in memory", async () => {
  installStorage({
    getItem() {
      throw new Error("blocked");
    },
    setItem() {
      throw new Error("quota");
    },
    removeItem() {},
  });
  const fresh = await import("../lib/auth.js?no-storage");
  assert.equal(fresh.loadSession(), null);
  fresh.saveSession(session());
  assert.equal(fresh.loadSession().token, "t-1");
  fresh.clearSession();
  assert.equal(fresh.loadSession(), null);
});

test("safeNext keeps same-site paths only", () => {
  assert.equal(safeNext("/groups/abc?tab=1"), "/groups/abc?tab=1");
  assert.equal(safeNext("//evil.example"), "/");
  assert.equal(safeNext("https://evil.example"), "/");
  assert.equal(safeNext("/\\evil.example"), "/");
  assert.equal(safeNext(undefined, "/groups"), "/groups");
  assert.equal(safeNext(["/a", "/b"]), "/");
});
