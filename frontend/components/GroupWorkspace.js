import Head from "next/head";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Header from "@/components/Header";
import { useAuth } from "@/lib/auth";

export default function GroupWorkspace({ children, title = "Groups", wide = false }) {
  const { loading, user } = useAuth();
  return <>
    <Head><title>{title} · Roomly</title></Head><Header />
    <main className={"group-workspace" + (wide ? " wide" : "")}>
      {loading ? <p role="status">Checking session…</p> : !user ? <section className="card group-empty">
        <h1>{title}</h1><p className="muted">Plan your search with up to five housemates.</p>
        <Link href="/sign-in"><a className="button">Sign in to see your groups</a></Link>
      </section> : user.role === "admin" ? <section className="card group-empty"><p className="muted">Administrator accounts can’t join groups.</p></section> : children(user)}
    </main>
  </>;
}

// Each workspace is keyed by account and resource. Late reads cannot replace newer results.
// Refreshing keeps the current data on screen so forms, selections and scroll survive a reload.
export function useGroupData(load) {
  const { authenticatedRequest } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [revision, setRevision] = useState(0);
  const lock = useRef(false);
  const source = useRef(null);
  const refresh = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => {
    let active = true;
    if (source.current !== load) {
      source.current = load;
      setData(null);
    }
    setError("");
    load(authenticatedRequest).then(result => { if (active) setData(result); })
      .catch(err => {
        if (!active) return;
        if ([403, 404].includes(err.status)) setData(null);
        setError(err.message);
      });
    return () => { active = false; };
  }, [load, authenticatedRequest, revision]);
  async function run(action) {
    if (lock.current) return;
    lock.current = true;
    setPending(true);
    setError("");
    try { await action(authenticatedRequest); }
    catch (err) {
      if ([403, 404].includes(err.status)) setData(null);
      setError(err.message);
    } finally { lock.current = false; setPending(false); }
  }
  return { data, error, pending, run, refresh, update: setData };
}

export function Feedback({ state }) {
  return state.error ? <p role="alert" className="group-alert">{state.error} <button type="button" className="link-button" onClick={state.refresh}>Try again</button></p>
    : !state.data ? <p role="status" className="muted">Loading…</p> : null;
}

export function Avatar({ name }) {
  const initials = (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join("");
  return <span className="group-avatar" aria-hidden="true">{initials}</span>;
}

export const shortDate = value => new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

const relative = typeof Intl !== "undefined" && Intl.RelativeTimeFormat ? new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }) : null;
export function When({ value }) {
  const date = new Date(value);
  const minutes = Math.round((date - Date.now()) / 60000);
  let text = date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  if (relative && Math.abs(minutes) < 60) text = minutes === 0 ? "just now" : relative.format(minutes, "minute");
  else if (relative && Math.abs(minutes) < 60 * 24) text = relative.format(Math.round(minutes / 60), "hour");
  return <time dateTime={value} title={date.toLocaleString()}>{text}</time>;
}
