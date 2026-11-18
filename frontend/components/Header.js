import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/lib/auth";

// Search and account routes are implemented; collaboration routes are planned.
export default function Header() {
  const { user, loading, error, signOut } = useAuth();
  const [pending, setPending] = useState(false);
  async function leave() {
    setPending(true);
    try { await signOut(); } finally { setPending(false); }
  }
  return (
    <header className="header">
      <Link href="/">
        <a className="brand">Roomly</a>
      </Link>
      <nav className="nav" aria-label="Main">
        <Link href="/">
          <a>Search</a>
        </Link>
        <Link href="/compare">
          <a>Compare</a>
        </Link>
        <Link href="/groups">
          <a>Groups</a>
        </Link>
        <Link href="/notifications">
          <a>Notifications</a>
        </Link>
        {loading ? <span role="status">Checking session…</span> : user ? <>
          <span>{user.display_name || user.email}</span>
          <button className="button secondary" onClick={leave} disabled={pending}>{pending ? "Signing out…" : "Sign out"}</button>
        </> : <Link href="/sign-in"><a className="button">Sign in</a></Link>}
        {error && <span className="error" role="alert">{error}</span>}
      </nav>
    </header>
  );
}
