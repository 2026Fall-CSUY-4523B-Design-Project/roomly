import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Env, InboundEmail } from "../src/env";
import { handleEmail, handleRequest, handleScheduled, RETENTION_DAYS } from "../src/index";
import { htmlToText, MAX_BODY_CHARS, MAX_PARSE_BYTES, toStoredMessage } from "../src/inbox/ingest";
import { handleInbox, PAGE_SIZE } from "../src/inbox/routes";
import { COOKIE, issueSession, MAX_FAILURES, verifySession } from "../src/inbox/session";
import { D1Store, type StoredMessage } from "../src/inbox/store";
import { memoryD1 } from "./d1";

const NOW = 1_800_000_000;
const KEY = "session-key-for-tests";
const PASSWORD = "correct horse battery";
const BASE = "https://mail.roomly.bid";

function mime(fields: { subject?: string; from?: string; text?: string; html?: string; attachment?: boolean }): string {
  const { subject = "Hello", from = "Maya <maya@example.com>", text, html, attachment } = fields;
  const headers = [`From: ${from}`, "To: demo@roomly.bid", `Subject: ${subject}`, "MIME-Version: 1.0"];
  if (attachment) {
    return [...headers, 'Content-Type: multipart/mixed; boundary="b"', "", "--b", "Content-Type: text/plain", "", text ?? "see attached",
      "--b", 'Content-Type: application/pdf; name="a.pdf"', 'Content-Disposition: attachment; filename="a.pdf"',
      "Content-Transfer-Encoding: base64", "", "JVBERi0=", "--b--", ""].join("\r\n");
  }
  if (html !== undefined && text === undefined) return [...headers, "Content-Type: text/html; charset=utf-8", "", html].join("\r\n");
  return [...headers, "Content-Type: text/plain; charset=utf-8", "", text ?? "body"].join("\r\n");
}

function inbound(raw: string, to = "demo@roomly.bid", rawSize = raw.length) {
  const state = { forwarded: [] as string[], rejected: [] as string[] };
  const message: InboundEmail = {
    from: "bounce@example.com",
    to,
    rawSize,
    headers: new Headers({ subject: "Header subject" }),
    raw: new Response(raw).body as ReadableStream<Uint8Array>,
    forward: async (target) => {
      state.forwarded.push(target);
    },
    setReject: (reason) => {
      state.rejected.push(reason);
    },
  };
  return { message, state };
}

function makeEnv(overrides: Partial<Env> = {}) {
  const db = memoryD1();
  const env = {
    EMAIL: { send: async () => ({ messageId: "x" }) },
    MAIL_SECRET: "s",
    APP_URL: "https://roomly.bid",
    MAIL_FROM: "Roomly <no-reply@roomly.bid>",
    SUPPORT_ADDRESS: "support@roomly.bid",
    MAIL_TRANSPORT: "email",
    DB: db,
    INBOX_PASSWORD: PASSWORD,
    INBOX_SESSION_KEY: KEY,
    ...overrides,
  } as Env;
  return { env, db, store: new D1Store(db) };
}

function stored(overrides: Partial<StoredMessage> = {}): StoredMessage {
  return {
    id: crypto.randomUUID(), receivedAt: "2026-11-20T12:00:00.000Z", envelopeFrom: "a@example.com", envelopeTo: "support@roomly.bid",
    fromName: "A", fromAddress: "a@example.com", subject: "Subject", body: "Body", size: 10, attachments: 0, truncated: false, readAt: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.spyOn(console, "log").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

describe("ingest", () => {
  it("keeps the text part and the headers", async () => {
    const { message } = inbound(mime({ subject: "Lease question", text: "Is the unit available?" }));
    const m = await toStoredMessage(message, new Date("2026-11-20T10:00:00Z"), "id-1");
    expect(m).toMatchObject({ id: "id-1", subject: "Lease question", body: "Is the unit available?", fromName: "Maya",
      fromAddress: "maya@example.com", envelopeTo: "demo@roomly.bid", attachments: 0, receivedAt: "2026-11-20T10:00:00.000Z" });
  });

  it("reduces an HTML-only message to text, never storing markup", async () => {
    const { message } = inbound(mime({ html: "<style>p{}</style><p>Hi <b>there</b></p><script>alert(1)</script><p>Bye &amp; thanks</p>" }));
    const m = await toStoredMessage(message);
    expect(m.body).toBe("Hi there\nBye & thanks");
    expect(htmlToText("<div>a</div><div>b</div>")).toBe("a\nb");
  });

  it("counts attachments without keeping them", async () => {
    const { message } = inbound(mime({ attachment: true }));
    expect((await toStoredMessage(message)).attachments).toBe(1);
  });

  it("cuts an enormous body and flags it", async () => {
    const { message } = inbound(mime({ text: "x".repeat(MAX_BODY_CHARS + 500) }));
    const m = await toStoredMessage(message);
    expect(m.body).toHaveLength(MAX_BODY_CHARS);
    expect(m.truncated).toBe(true);
  });

  it("does not parse a message over the size limit", async () => {
    const { message } = inbound("From: a@example.com\r\n\r\nx", "demo@roomly.bid", MAX_PARSE_BYTES + 1);
    const m = await toStoredMessage(message);
    expect(m.body).toContain("not stored");
    expect(m.subject).toBe("Header subject");
    expect(m.truncated).toBe(true);
  });

  it("strips control characters from header fields", async () => {
    const { message } = inbound(mime({ subject: "bad\u0007subject" }));
    expect((await toStoredMessage(message)).subject).toBe("bad subject");
  });
});

describe("store", () => {
  it("lists newest first with totals and unread counts", async () => {
    const { store } = makeEnv();
    await store.insert(stored({ id: "00000000-0000-0000-0000-000000000001", receivedAt: "2026-11-20T10:00:00.000Z", subject: "old" }));
    await store.insert(stored({ id: "00000000-0000-0000-0000-000000000002", receivedAt: "2026-11-20T11:00:00.000Z", subject: "new" }));
    await store.markRead("00000000-0000-0000-0000-000000000001", "2026-11-20T12:00:00.000Z");
    const page = await store.list({ limit: 10, offset: 0 });
    expect(page.messages.map((m) => m.subject)).toEqual(["new", "old"]);
    expect([page.total, page.unread]).toEqual([2, 1]);
    expect(await store.list({ limit: 1, offset: 1 })).toMatchObject({ total: 2, messages: [{ subject: "old" }] });
  });

  it("filters by recipient and searches without treating % or _ as wildcards", async () => {
    const { store } = makeEnv();
    await store.insert(stored({ subject: "50% off", envelopeTo: "a@roomly.bid" }));
    await store.insert(stored({ subject: "500 units", envelopeTo: "b@roomly.bid" }));
    expect((await store.list({ to: "A@roomly.bid", limit: 10, offset: 0 })).total).toBe(1);
    expect((await store.list({ q: "50%", limit: 10, offset: 0 })).messages.map((m) => m.subject)).toEqual(["50% off"]);
    expect((await store.list({ q: "5_0", limit: 10, offset: 0 })).total).toBe(0);
    expect(await store.recipients()).toHaveLength(2);
  });

  it("purges old mail and stale login failures", async () => {
    const { store } = makeEnv();
    await store.insert(stored({ receivedAt: "2026-01-01T00:00:00.000Z" }));
    await store.insert(stored({ receivedAt: "2026-11-01T00:00:00.000Z" }));
    await store.recordFailure("1.1.1.1", 100);
    expect(await store.purgeOlderThan("2026-06-01T00:00:00.000Z", 1000)).toBe(1);
    expect((await store.list({ limit: 10, offset: 0 })).total).toBe(1);
    expect(await store.recentFailures("1.1.1.1", 0)).toBe(0);
  });
});

describe("session cookie", () => {
  it("accepts its own cookie and rejects forged, expired and malformed ones", async () => {
    const cookie = await issueSession(KEY, NOW);
    expect(await verifySession(KEY, cookie, NOW + 10)).toBe(true);
    expect(await verifySession(KEY, cookie, NOW + 13 * 3600)).toBe(false);
    expect(await verifySession("other-key", cookie, NOW + 10)).toBe(false);
    const [, digest] = cookie.split(".");
    expect(await verifySession(KEY, `${NOW + 999_999}.${digest}`, NOW)).toBe(false);
    for (const bad of [undefined, "", "abc", "1.", ".2", "x.y"]) expect(await verifySession(KEY, bad, NOW)).toBe(false);
  });
});

describe("web inbox", () => {
  async function loginCookie(env: Env, password = PASSWORD, ip = "9.9.9.9") {
    const response = await handleInbox(new Request(`${BASE}/login`, {
      method: "POST", headers: { "content-type": "application/x-www-form-urlencoded", origin: BASE, "cf-connecting-ip": ip },
      body: new URLSearchParams({ password }).toString(),
    }), env, NOW);
    return { response: response as Response, cookie: (response?.headers.get("set-cookie") ?? "").split(";")[0] ?? "" };
  }
  const get = (env: Env, path: string, cookie = "") =>
    handleInbox(new Request(`${BASE}${path}`, { headers: cookie ? { cookie } : {} }), env, NOW) as Promise<Response>;

  it("is closed until it is configured", async () => {
    const { env } = makeEnv({ INBOX_PASSWORD: undefined });
    expect((await get(env, "/inbox")).status).toBe(503);
    expect((await get(makeEnv({ DB: undefined }).env, "/login")).status).toBe(503);
  });

  it("sends anonymous visitors to the login page and never lists mail to them", async () => {
    const { env, store } = makeEnv();
    await store.insert(stored({ subject: "secret subject" }));
    for (const path of ["/inbox", "/", "/m/00000000-0000-0000-0000-000000000001"]) {
      const response = await get(env, path);
      expect([response.status, response.headers.get("location")]).toEqual([303, "/login"]);
    }
    expect(await (await get(env, "/login")).text()).not.toContain("secret subject");
  });

  it("logs in with the right password and sets a hardened cookie", async () => {
    const { env } = makeEnv();
    const { response } = await loginCookie(env);
    expect([response.status, response.headers.get("location")]).toEqual([303, "/inbox"]);
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(cookie).toMatch(new RegExp(`^${COOKIE}=\\d+\\.[0-9a-f]{64};`));
    for (const flag of ["HttpOnly", "SameSite=Strict", "Secure", "Path=/"]) expect(cookie).toContain(flag);
  });

  it("rejects a wrong password, then throttles after repeated failures", async () => {
    const { env } = makeEnv();
    for (let i = 0; i < MAX_FAILURES; i += 1) expect((await loginCookie(env, "nope")).response.status).toBe(401);
    const blocked = (await loginCookie(env, PASSWORD)).response;
    expect(blocked.status).toBe(429);
    expect(blocked.headers.get("retry-after")).toBe("900");
    // Another address is not affected.
    expect((await loginCookie(env, PASSWORD, "8.8.8.8")).response.status).toBe(303);
  });

  it("refuses a login or delete that does not come from this site", async () => {
    const { env, store } = makeEnv();
    const m = stored();
    await store.insert(m);
    const cross = await handleInbox(new Request(`${BASE}/login`, {
      method: "POST", headers: { "content-type": "application/x-www-form-urlencoded", origin: "https://evil.example" },
      body: `password=${PASSWORD}`,
    }), env, NOW);
    expect(cross?.status).toBe(403);
    const { cookie } = await loginCookie(env);
    const forged = await handleInbox(new Request(`${BASE}/m/${m.id}/delete`, { method: "POST", headers: { cookie, origin: "https://evil.example" } }), env, NOW);
    expect(forged?.status).toBe(403);
    expect(await store.get(m.id)).not.toBeNull();
  });

  it("lists mail, escapes every hostile value and sends a strict CSP", async () => {
    const { env, store } = makeEnv();
    const evil = '<img src=x onerror=alert(1)>';
    const m = stored({ subject: evil, fromName: evil, body: `<script>alert(1)</script>${evil}`, envelopeTo: `"><svg onload=1>@roomly.bid` });
    await store.insert(m);
    const { cookie } = await loginCookie(env);
    const list = await get(env, "/inbox", cookie);
    const view = await get(env, `/m/${m.id}`, cookie);
    for (const response of [list, view]) {
      const body = await response.text();
      expect(body).not.toContain("<img src=x");
      expect(body).not.toContain("<script>alert");
      expect(body).not.toContain("<svg onload");
      expect(body).toContain("&lt;");
      expect(response.headers.get("content-security-policy")).toContain("default-src 'none'");
      expect(response.headers.get("cache-control")).toBe("no-store");
      expect(response.headers.get("x-frame-options")).toBe("DENY");
    }
  });

  it("marks a message read when opened and deletes on request", async () => {
    const { env, store } = makeEnv();
    const m = stored();
    await store.insert(m);
    const { cookie } = await loginCookie(env);
    expect((await store.get(m.id))?.readAt).toBeNull();
    expect((await get(env, `/m/${m.id}`, cookie)).status).toBe(200);
    expect((await store.get(m.id))?.readAt).not.toBeNull();
    const removed = await handleInbox(new Request(`${BASE}/m/${m.id}/delete`, { method: "POST", headers: { cookie, origin: BASE } }), env, NOW);
    expect(removed?.status).toBe(303);
    expect(await store.get(m.id)).toBeNull();
    expect((await get(env, `/m/${m.id}`, cookie)).status).toBe(404);
  });

  it("paginates, filters and ignores a malformed page number", async () => {
    const { env, store } = makeEnv();
    for (let i = 0; i < PAGE_SIZE + 5; i += 1) await store.insert(stored({ receivedAt: `2026-11-20T10:${String(i).padStart(2, "0")}:00.000Z`, subject: `m${i}` }));
    const { cookie } = await loginCookie(env);
    expect(await (await get(env, "/inbox", cookie)).text()).toContain("Page 1 of 2");
    expect(await (await get(env, "/inbox?page=2", cookie)).text()).toContain("Page 2 of 2");
    expect((await get(env, "/inbox?page=abc", cookie)).status).toBe(200);
    expect(await (await get(env, "/inbox?q=m1&to=support@roomly.bid", cookie)).text()).toContain("messages");
  });

  it("signs out by clearing the cookie", async () => {
    const { env } = makeEnv();
    const { cookie } = await loginCookie(env);
    const out = await handleInbox(new Request(`${BASE}/logout`, { method: "POST", headers: { cookie, origin: BASE } }), env, NOW);
    expect(out?.headers.get("set-cookie")).toContain("Max-Age=0");
  });

  it("is reachable through the Worker's fetch handler and leaves other paths a 404", async () => {
    const { env } = makeEnv();
    expect((await handleRequest(new Request(`${BASE}/login`), env, NOW)).status).toBe(200);
    expect((await handleRequest(new Request(`${BASE}/nowhere`), env, NOW)).status).toBe(404);
  });
});

describe("handleEmail with the inbox", () => {
  it("stores every message, whichever address it was sent to", async () => {
    const { env, store } = makeEnv();
    for (const to of ["support@roomly.bid", "anything@roomly.bid", "no-reply@roomly.bid"]) {
      await handleEmail(inbound(mime({ subject: `to ${to}` }), to).message, env);
    }
    const page = await store.list({ limit: 10, offset: 0 });
    expect(page.messages.map((m) => m.envelopeTo).sort()).toEqual(["anything@roomly.bid", "no-reply@roomly.bid", "support@roomly.bid"]);
  });

  it("also forwards to the private inbox when one is configured, except automated senders", async () => {
    const { env, store } = makeEnv({ SUPPORT_INBOX: "me@example.net" });
    const human = inbound(mime({}), "support@roomly.bid");
    const bounce = inbound(mime({}), "bounce@roomly.bid");
    await handleEmail(human.message, env);
    await handleEmail(bounce.message, env);
    expect(human.state.forwarded).toEqual(["me@example.net"]);
    expect(bounce.state.forwarded).toEqual([]);
    expect((await store.list({ limit: 10, offset: 0 })).total).toBe(2);
  });

  it("asks the sender to retry when the message could be neither stored nor forwarded", async () => {
    const { env } = makeEnv();
    env.DB = { prepare: () => { throw new Error("D1 down"); } };
    const { message, state } = inbound(mime({}));
    await handleEmail(message, env);
    expect(state.rejected).toHaveLength(1);
  });

  it("does not reject when the forward still delivered it", async () => {
    const { env } = makeEnv({ SUPPORT_INBOX: "me@example.net" });
    env.DB = { prepare: () => { throw new Error("D1 down"); } };
    const { message, state } = inbound(mime({}), "support@roomly.bid");
    await handleEmail(message, env);
    expect([state.forwarded, state.rejected]).toEqual([["me@example.net"], []]);
  });

  it("works without a database: forwarding only, nothing rejected", async () => {
    const { env } = makeEnv({ DB: undefined, SUPPORT_INBOX: "me@example.net" });
    const { message, state } = inbound(mime({}), "support@roomly.bid");
    await handleEmail(message, env);
    expect([state.forwarded, state.rejected]).toEqual([["me@example.net"], []]);
  });
});

describe("retention", () => {
  it("purges mail older than the window", async () => {
    const { env, store } = makeEnv();
    const now = new Date("2026-11-20T00:00:00Z");
    const old = new Date(now.getTime() - (RETENTION_DAYS + 1) * 86_400_000).toISOString();
    const recent = new Date(now.getTime() - (RETENTION_DAYS - 1) * 86_400_000).toISOString();
    await store.insert(stored({ receivedAt: old }));
    await store.insert(stored({ receivedAt: recent }));
    await handleScheduled(env, now);
    expect((await store.list({ limit: 10, offset: 0 })).total).toBe(1);
  });
});
