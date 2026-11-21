/**
 * The inbox's HTML. Every dynamic value goes through `esc`, no script runs, and the response CSP
 * (routes.ts) forbids everything but this inline stylesheet, so a hostile message can show text and
 * nothing else.
 */

import type { MessageSummary, Page, StoredMessage } from "./store";

export function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const CSS = `
:root{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--accent:#1f2937;--danger:#b42318}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b22;--text:#e5e7eb;--muted:#9ca3af;--line:#2a2f3a;--accent:#e5e7eb;--danger:#f97066}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{display:flex;gap:16px;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--line);background:var(--card)}
header a{color:inherit;text-decoration:none;font-weight:600}main{max-width:980px;margin:24px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}tr:last-child td{border-bottom:0}
.unread td{font-weight:600}.muted{color:var(--muted);font-size:13px}.pill{display:inline-block;padding:2px 8px;border:1px solid var(--line);border-radius:999px;font-size:12px;color:var(--muted);text-decoration:none;margin:0 6px 6px 0}
input[type=text],input[type=search],input[type=password]{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:inherit}
button{padding:9px 16px;border:1px solid var(--accent);border-radius:8px;background:var(--accent);color:var(--bg);font:inherit;cursor:pointer}
button.quiet{background:transparent;color:var(--text);border-color:var(--line)}button.danger{background:transparent;color:var(--danger);border-color:var(--danger)}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.row>input{flex:1;min-width:180px}
pre{white-space:pre-wrap;word-wrap:break-word;overflow-wrap:anywhere;margin:16px 0 0;font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
dl{display:grid;grid-template-columns:90px 1fr;gap:6px 12px;margin:0}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}
.error{color:var(--danger)}form.inline{display:inline}
`;

function layout(title: string, body: string, signedIn: boolean): string {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>${esc(title)} · Roomly inbox</title><style>${CSS}</style></head>
<body><header><a href="/inbox">Roomly inbox</a>${
    signedIn ? `<form class="inline" method="post" action="/logout"><button class="quiet">Sign out</button></form>` : ""
  }</header><main>${body}</main></body></html>`;
}

export function loginPage(message = ""): string {
  return layout(
    "Sign in",
    `<div class="card" style="max-width:380px;margin:48px auto"><h1 style="margin-top:0;font-size:20px">Sign in</h1>
<form method="post" action="/login"><p><input type="password" name="password" placeholder="Password" autocomplete="current-password" autofocus required></p>
${message ? `<p class="error" role="alert">${esc(message)}</p>` : ""}<button>Sign in</button></form></div>`,
    false,
  );
}

export function notConfiguredPage(): string {
  return layout("Not configured", `<div class="card"><p>The inbox is not configured on this Worker yet.</p></div>`, false);
}

export function errorPage(): string {
  return layout("Error", `<div class="card"><p class="error">Something went wrong. Try again in a moment.</p><p><a href="/inbox">← Inbox</a></p></div>`, false);
}

export function notFoundPage(): string {
  return layout("Not found", `<p><a href="/inbox">← Inbox</a></p><div class="card"><p>Nothing here.</p></div>`, true);
}

function when(iso: string): string {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}

function sender(m: MessageSummary): string {
  return m.fromName ? `${m.fromName} <${m.fromAddress}>` : m.fromAddress || m.envelopeFrom;
}

export interface ListView {
  page: Page;
  recipients: { address: string; count: number }[];
  to: string;
  q: string;
  pageNumber: number;
  pageSize: number;
}

function href(params: { to?: string; q?: string; page?: number }): string {
  const search = new URLSearchParams();
  if (params.to) search.set("to", params.to);
  if (params.q) search.set("q", params.q);
  if (params.page && params.page > 1) search.set("page", String(params.page));
  const text = search.toString();
  return `/inbox${text ? `?${text}` : ""}`;
}

export function inboxPage(view: ListView): string {
  const { page, recipients, to, q, pageNumber, pageSize } = view;
  const pages = Math.max(1, Math.ceil(page.total / pageSize));
  const rows = page.messages
    .map(
      (m) => `<tr class="${m.readAt ? "" : "unread"}"><td>${esc(when(m.receivedAt))}</td>
<td>${esc(sender(m))}</td><td><a href="${href({ to: m.envelopeTo })}" class="muted">${esc(m.envelopeTo)}</a></td>
<td><a href="/m/${esc(m.id)}">${esc(m.subject || "(no subject)")}</a></td></tr>`,
    )
    .join("");
  const filters = recipients
    .map((r) => `<a class="pill" href="${esc(href({ to: r.address }))}">${esc(r.address)} · ${r.count}</a>`)
    .join("");
  const pager =
    pages > 1
      ? `<p class="row">${pageNumber > 1 ? `<a href="${esc(href({ to, q, page: pageNumber - 1 }))}">← Newer</a>` : ""}
<span class="muted">Page ${pageNumber} of ${pages}</span>${pageNumber < pages ? `<a href="${esc(href({ to, q, page: pageNumber + 1 }))}">Older →</a>` : ""}</p>`
      : "";
  return layout(
    "Inbox",
    `<div class="card"><form class="row" method="get" action="/inbox"><input type="search" name="q" value="${esc(q)}" placeholder="Search sender, recipient or subject">
${to ? `<input type="hidden" name="to" value="${esc(to)}">` : ""}<button>Search</button>${to || q ? `<a href="/inbox">Clear</a>` : ""}</form>
<p class="muted">${page.total} message${page.total === 1 ? "" : "s"}, ${page.unread} unread${to ? ` · to ${esc(to)}` : ""}</p>${filters ? `<p>${filters}</p>` : ""}
${page.total === 0 ? `<p class="muted">Nothing here yet. Mail sent to any @roomly.bid address lands in this list.</p>` : `<table><thead><tr><th>Received</th><th>From</th><th>To</th><th>Subject</th></tr></thead><tbody>${rows}</tbody></table>`}${pager}</div>`,
    true,
  );
}

export function messagePage(m: StoredMessage): string {
  return layout(
    m.subject || "(no subject)",
    `<p><a href="/inbox">← Inbox</a></p><div class="card"><h1 style="margin-top:0;font-size:20px">${esc(m.subject || "(no subject)")}</h1>
<dl><dt>From</dt><dd>${esc(m.fromName ? `${m.fromName} <${m.fromAddress}>` : m.fromAddress)}</dd>
<dt>Envelope</dt><dd>${esc(m.envelopeFrom)} → ${esc(m.envelopeTo)}</dd><dt>Received</dt><dd>${esc(when(m.receivedAt))}</dd>
<dt>Size</dt><dd>${m.size} bytes${m.attachments > 0 ? ` · ${m.attachments} attachment${m.attachments === 1 ? "" : "s"} not stored` : ""}${m.truncated ? " · body cut short" : ""}</dd></dl>
<pre>${esc(m.body || "(no text content)")}</pre>
<form method="post" action="/m/${esc(m.id)}/delete" style="margin-top:20px"><button class="danger">Delete</button></form></div>`,
    true,
  );
}
