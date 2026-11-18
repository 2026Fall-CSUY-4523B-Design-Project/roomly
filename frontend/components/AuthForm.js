import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";

import Header from "@/components/Header";
import { useAuth } from "@/lib/auth";

export default function AuthForm({ signUp = false }) {
  const { signIn, user, loading } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const title = signUp ? "Create an account" : "Sign in";

  async function submit(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const body = { email: data.get("email"), password: data.get("password") };
    if (signUp && data.get("display_name").trim()) body.display_name = data.get("display_name").trim();
    try {
      await signIn(signUp ? "/auth/sign-up" : "/auth/sign-in", body);
      await router.replace("/");
    } catch (err) {
      setError(err.message || "Could not connect. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return <>
    <Head><title>{title} · Roomly</title></Head>
    <Header />
    <main className="auth-panel card">
      <h1>{title}</h1>
      {loading ? <p role="status">Checking session…</p> : user ? <p>You are signed in as {user.email}. <Link href="/"><a>Browse listings</a></Link></p> : <>
        <form onSubmit={submit} className="auth-form">
          {signUp && <label>Display name (optional)<input name="display_name" autoComplete="nickname" maxLength={60} disabled={pending} /></label>}
          <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254} disabled={pending} /></label>
          <label>Password<input name="password" type="password" autoComplete={signUp ? "new-password" : "current-password"} required minLength={signUp ? 8 : 1} maxLength={128} disabled={pending} /></label>
          {signUp && <p className="muted">Use 8–128 characters.</p>}
          {error && <p className="error" role="alert">{error}</p>}
          <button className="button" disabled={pending}>{pending ? "Please wait…" : title}</button>
        </form>
        <p>{signUp ? "Already have an account? " : "New to Roomly? "}<Link href={signUp ? "/sign-in" : "/sign-up"}><a>{signUp ? "Sign in" : "Create an account"}</a></Link></p>
      </>}
    </main>
  </>;
}
