import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import Header from "@/components/Header";
import { useAuth } from "@/lib/auth";

// Signed-in pages outside groups. `back` sits above the heading, `action` beside it;
// pass `heading={false}` when the page renders its own heading from loaded data.
export default function AccountWorkspace({ title, back, action, heading = true, wide = false, children }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const signedIn = !loading && router.isReady && user;
  return <>
    <Head><title>{title} · Roomly</title></Head>
    <Header />
    <main className={"group-workspace account-workspace" + (wide ? " wide" : "")}>
      {back && <Link href={back.href}><a className="back-link">← {back.label}</a></Link>}
      {(heading || !signedIn) && <div className="account-title"><h1>{title}</h1>{signedIn && action}</div>}
      {loading || !router.isReady ? <p role="status" className="muted">Loading…</p> : user ? children(user) :
        <section className="card account-signed-out">
          <p>Sign in to see this page.</p>
          <Link href={{ pathname: "/sign-in", query: { next: router.asPath } }}><a className="button">Sign in</a></Link>
        </section>}
    </main>
  </>;
}
