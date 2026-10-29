import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";

import { api } from "@/lib/api";
import { clearSession } from "@/lib/auth";
import { useSession } from "@/lib/useSession";

import styles from "./Layout.module.css";

const NAV = [
  { href: "/", label: "Search" },
  { href: "/compare", label: "Compare" },
  { href: "/groups", label: "Groups" },
  { href: "/notifications", label: "Notifications" },
];

function isActive(pathname, href) {
  return href === "/" ? pathname === "/" || pathname.startsWith("/listings") : pathname.startsWith(href);
}

export default function Layout({ children }) {
  const router = useRouter();
  const { session, ready } = useSession();
  const [signingOut, setSigningOut] = useState(false);
  const nav = session?.user.role === "admin" ? [...NAV, { href: "/admin", label: "Admin" }] : NAV;

  async function signOut() {
    setSigningOut(true);
    try {
      await api.signOut();
    } catch (err) {
      console.warn("[roomly] sign-out request failed; clearing the local session anyway", err);
    }
    clearSession();
    setSigningOut(false);
    router.push("/");
  }

  return (
    <div className={styles.shell}>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <div className={`container ${styles.bar}`}>
          <Link href="/">
            <a className={styles.brand} aria-label="Roomly home">
              <span className={styles.mark} aria-hidden="true">
                R
              </span>
              Roomly
            </a>
          </Link>
          <nav className={styles.nav} aria-label="Main">
            {nav.map((item) => (
              <Link key={item.href} href={item.href}>
                <a
                  className={styles.link}
                  aria-current={isActive(router.pathname, item.href) ? "page" : undefined}
                >
                  {item.label}
                </a>
              </Link>
            ))}
          </nav>
          <div className={styles.account}>
            {!ready ? null : session ? (
              <>
                <span className={styles.who} title={session.user.email}>
                  {session.user.display_name || session.user.email}
                </span>
                <button className="btn btn-ghost" onClick={signOut} disabled={signingOut}>
                  {signingOut ? "Signing out…" : "Sign out"}
                </button>
              </>
            ) : (
              <>
                <Link href={`/sign-in?next=${encodeURIComponent(router.asPath)}`}>
                  <a className="btn btn-quiet">Sign in</a>
                </Link>
                <Link href="/sign-up">
                  <a className="btn btn-primary">Create account</a>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>
      <main id="main" className={styles.main}>
        {children}
      </main>
      <footer className={styles.footer}>
        <div className={`container ${styles.footRow}`}>
          <span>Roomly · apartment hunting for the whole group</span>
          <span>CS 4523 · Team A13 · Release 1 in progress</span>
        </div>
      </footer>
    </div>
  );
}
