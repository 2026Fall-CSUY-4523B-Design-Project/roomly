/** HTTP routes of the web inbox: /login, /logout, /inbox, /m/:id. */

import type { Env } from "../env";
import { errorPage, inboxPage, loginPage, messagePage, notConfiguredPage, notFoundPage } from "./pages";
import { attemptLogin, COOKIE, issueSession, readCookie, SESSION_SECONDS, verifySession } from "./session";
import { D1Store, type InboxStore } from "./store";

export const PAGE_SIZE = 50;
const MAX_FORM_BYTES = 4096;

const SECURITY_HEADERS: Record<string, string> = {
  "content-type": "text/html; charset=utf-8",
  "cache-control": "no-store",
  "content-security-policy":
    "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
  "x-content-type-options": "nosniff",
  "x-frame-options": "DENY",
  "referrer-policy": "no-referrer",
  "x-robots-tag": "noindex, nofollow",
};

function html(status: number, body: string, extra: Record<string, string | string[]> = {}): Response {
  const headers = new Headers(SECURITY_HEADERS);
  for (const [name, value] of Object.entries(extra)) {
    for (const v of Array.isArray(value) ? value : [value]) headers.append(name, v);
  }
  return new Response(body, { status, headers });
}

function redirect(location: string, extra: Record<string, string> = {}): Response {
  return html(303, "", { location, ...extra });
}

function sessionCookie(value: string, maxAge: number, secure: boolean): string {
  return `${COOKIE}=${value}; Path=/; Max-Age=${maxAge}; HttpOnly; SameSite=Strict${secure ? "; Secure" : ""}`;
}

/**
 * A state-changing request must come from this site. Browsers say so themselves in `Sec-Fetch-Site`
 * (a page cannot forge it), and that is checked first: under `Referrer-Policy: no-referrer` they send
 * `Origin: null` on same-origin form posts, which must not count against the user. Without that
 * header (older browsers, scripts) fall back to a parseable `Origin` on this host. SameSite=Strict on
 * the cookie is the second layer.
 */
export function sameOrigin(request: Request): boolean {
  const site = request.headers.get("sec-fetch-site");
  if (site) return site === "same-origin";
  const origin = request.headers.get("origin");
  if (!origin || origin === "null") return false;
  try {
    return new URL(origin).host === new URL(request.url).host;
  } catch {
    return false;
  }
}

async function form(request: Request): Promise<URLSearchParams | null> {
  const type = request.headers.get("content-type") ?? "";
  if (!type.startsWith("application/x-www-form-urlencoded")) return null;
  const text = await request.text();
  return text.length > MAX_FORM_BYTES ? null : new URLSearchParams(text);
}

/** `null` when the path is not an inbox route, so the caller can answer 404. Never throws. */
export async function handleInbox(
  request: Request,
  env: Env,
  nowSeconds: number = Math.floor(Date.now() / 1000),
  store: InboxStore | undefined = env.DB ? new D1Store(env.DB) : undefined,
): Promise<Response | null> {
  try {
    return await route(request, env, nowSeconds, store);
  } catch (error) {
    console.error(JSON.stringify({ event: "inbox_error", path: new URL(request.url).pathname, message: String(error) }));
    return html(500, errorPage());
  }
}

async function route(
  request: Request,
  env: Env,
  nowSeconds: number = Math.floor(Date.now() / 1000),
  store: InboxStore | undefined = env.DB ? new D1Store(env.DB) : undefined,
): Promise<Response | null> {
  const url = new URL(request.url);
  const path = url.pathname;
  const isInboxPath = path === "/" || path === "/login" || path === "/logout" || path === "/inbox" || path.startsWith("/m/");
  if (!isInboxPath) return null;

  const secure = url.protocol === "https:";
  const open = env.INBOX_AUTH === "off";
  if (!store) return html(503, notConfiguredPage());
  if (open) return openRoute(request, url, store, nowSeconds);
  if (!env.INBOX_PASSWORD || !env.INBOX_SESSION_KEY) return html(503, notConfiguredPage());
  const key = env.INBOX_SESSION_KEY;
  const signedIn = await verifySession(key, readCookie(request.headers.get("cookie"), COOKIE), nowSeconds);

  if (path === "/login") {
    if (request.method === "GET") return signedIn ? redirect("/inbox") : html(200, loginPage());
    if (request.method !== "POST") return html(405, loginPage("Use the form."), { allow: "GET, POST" });
    if (!sameOrigin(request)) return html(403, loginPage("Request rejected."));
    const body = await form(request);
    const ip = request.headers.get("cf-connecting-ip") ?? "unknown";
    const outcome = body
      ? await attemptLogin(store, key, env.INBOX_PASSWORD, body.get("password") ?? "", ip, nowSeconds)
      : "wrong";
    if (outcome === "throttled") {
      console.warn(JSON.stringify({ event: "inbox_login_throttled", ip }));
      return html(429, loginPage("Too many attempts. Try again in a few minutes."), { "retry-after": "900" });
    }
    if (outcome === "wrong") {
      console.warn(JSON.stringify({ event: "inbox_login_failed", ip }));
      return html(401, loginPage("Wrong password."));
    }
    console.log(JSON.stringify({ event: "inbox_login", ip }));
    return redirect("/inbox", { "set-cookie": sessionCookie(await issueSession(key, nowSeconds), SESSION_SECONDS, secure) });
  }

  if (path === "/logout") {
    if (request.method !== "POST") return html(405, loginPage(), { allow: "POST" });
    if (!sameOrigin(request)) return html(403, loginPage("Request rejected."));
    return redirect("/login", { "set-cookie": sessionCookie("", 0, secure) });
  }

  if (!signedIn) return redirect("/login");

  if (path === "/") return redirect("/inbox");

  if (path === "/inbox") return listing(request, url, store, false);

  const match = /^\/m\/([0-9a-f-]{36})(\/delete)?$/.exec(path);
  if (!match) return html(404, notFoundPage());
  const id = match[1] as string;

  if (match[2]) {
    if (request.method !== "POST") return html(405, "", { allow: "POST" });
    if (!sameOrigin(request)) return html(403, loginPage("Request rejected."));
    const removed = await store.remove(id);
    console.log(JSON.stringify({ event: "inbox_delete", id, removed }));
    return redirect("/inbox");
  }

  return viewMessage(request, store, id, false, nowSeconds);
}

async function listing(request: Request, url: URL, store: InboxStore, open: boolean): Promise<Response> {
  if (request.method !== "GET") return html(405, "", { allow: "GET" });
  const to = (url.searchParams.get("to") ?? "").trim().slice(0, 254);
  const q = (url.searchParams.get("q") ?? "").trim().slice(0, 100);
  const pageNumber = Math.max(1, Math.min(10_000, Number.parseInt(url.searchParams.get("page") ?? "1", 10) || 1));
  const [page, recipients] = await Promise.all([
    store.list({ to: to || undefined, q: q || undefined, limit: PAGE_SIZE, offset: (pageNumber - 1) * PAGE_SIZE }),
    store.recipients(),
  ]);
  return html(200, inboxPage({ page, recipients, to, q, pageNumber, pageSize: PAGE_SIZE, open }));
}

async function viewMessage(request: Request, store: InboxStore, id: string, open: boolean, nowSeconds: number): Promise<Response> {
  if (request.method !== "GET") return html(405, "", { allow: "GET" });
  const message = await store.get(id);
  if (!message) return html(404, notFoundPage());
  // In open mode a visitor must not change anything, not even what counts as read.
  if (!open && !message.readAt) await store.markRead(id, new Date(nowSeconds * 1000).toISOString());
  return html(200, messagePage(message, open));
}

/** Demo mode (INBOX_AUTH=off): no login, read-only. */
async function openRoute(request: Request, url: URL, store: InboxStore, nowSeconds: number): Promise<Response> {
  const path = url.pathname;
  if (path === "/" || path === "/login" || path === "/logout") return redirect("/inbox");
  if (path === "/inbox") return listing(request, url, store, true);
  const match = /^\/m\/([0-9a-f-]{36})(\/delete)?$/.exec(path);
  if (!match) return html(404, notFoundPage());
  if (match[2]) return html(403, errorPage("The demo inbox is read-only."));
  return viewMessage(request, store, match[1] as string, true, nowSeconds);
}

