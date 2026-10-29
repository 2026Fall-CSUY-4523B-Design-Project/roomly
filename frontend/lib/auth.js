// The signed-in session ({ token, expires_at, user }) from POST /auth/sign-in or /auth/sign-up.
// Kept in localStorage so a reload stays signed in. Storage can be missing or throw (private
// windows, blocked site data, server rendering); then the session lives in memory until the
// tab closes.

const KEY = "roomly.session";
const listeners = new Set();
let memory = null;
let storageBroken = false;

function storage() {
  if (storageBroken) return null;
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function forget() {
  memory = null;
  try {
    storage()?.removeItem(KEY);
  } catch {
    // nothing stored, nothing to clear
  }
}

export function loadSession() {
  let session = memory;
  try {
    const store = storage();
    if (store) session = JSON.parse(store.getItem(KEY) ?? "null");
  } catch {
    // unreadable: keep the in-memory copy
  }
  if (session?.token && new Date(session.expires_at) > new Date()) return session;
  if (session) forget(); // expired
  return null;
}

export function saveSession(session) {
  memory = session;
  try {
    storage()?.setItem(KEY, JSON.stringify(session));
  } catch (err) {
    storageBroken = true;
    console.warn("[roomly] could not persist the session; it lasts until this tab closes", err);
  }
  notify(session);
}

export function clearSession() {
  forget();
  notify(null);
}

// Calls fn(session | null) on sign-in and sign-out, in this tab and in other tabs.
export function onSessionChange(fn) {
  listeners.add(fn);
  const fromOtherTab = (event) => {
    if (event.key === KEY || event.key === null) fn(loadSession());
  };
  globalThis.addEventListener?.("storage", fromOtherTab);
  return () => {
    listeners.delete(fn);
    globalThis.removeEventListener?.("storage", fromOtherTab);
  };
}

function notify(session) {
  for (const fn of listeners) fn(session);
}

// Only same-site paths survive a ?next= redirect, so a crafted link cannot bounce elsewhere.
export function safeNext(next, fallback = "/") {
  return typeof next === "string" && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\")
    ? next
    : fallback;
}
