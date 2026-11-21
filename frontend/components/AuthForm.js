import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";

import AuthPage from "@/components/AuthPage";
import ResendVerification from "@/components/ResendVerification";
import { signUp as createAccount } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AuthForm({ signUp = false }) {
  const { signIn, user, loading } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  // The address awaiting confirmation: set after sign-up, or when sign-in is refused as unverified.
  const [unconfirmed, setUnconfirmed] = useState(null);
  const title = signUp ? "Create an account" : "Sign in";

  async function submit(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const body = { email: data.get("email"), password: data.get("password") };
    if (signUp && data.get("display_name").trim()) body.display_name = data.get("display_name").trim();
    try {
      if (signUp) {
        const result = await createAccount(body);
        setUnconfirmed({ email: result.email, sent: result.verification_sent, fresh: true });
      } else {
        await signIn("/auth/sign-in", body);
        await router.replace("/");
      }
    } catch (err) {
      if (err.code === "email_not_verified") setUnconfirmed({ email: body.email.trim().toLowerCase(), sent: false, fresh: false });
      else setError(err.message || "Could not connect. Please try again.");
    } finally {
      setPending(false);
    }
  }

  if (unconfirmed) return <AuthPage title="Check your email">
    {unconfirmed.fresh && !unconfirmed.sent
      ? <p className="error" role="alert">Your account is created, but we could not send the confirmation email. Try sending it again.</p>
      : unconfirmed.fresh
        ? <p role="status">We sent a confirmation link to <strong>{unconfirmed.email}</strong>. Open it to finish setting up your account; it works for 24 hours.</p>
        : <p role="alert">Confirm <strong>{unconfirmed.email}</strong> before signing in. Open the link we emailed you, or ask for a new one.</p>}
    <ResendVerification email={unconfirmed.email} />
    <p><Link href="/sign-in"><a>Back to sign in</a></Link></p>
  </AuthPage>;

  return <AuthPage title={title}>
    {loading ? <p role="status">Checking session…</p> : user ? <p>You are signed in as {user.email}. <Link href="/"><a>Browse listings</a></Link></p> : <>
      <form onSubmit={submit} className="auth-form">
        {signUp && <label>Display name (optional)<input name="display_name" autoComplete="nickname" maxLength={60} disabled={pending} /></label>}
        <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254} disabled={pending} /></label>
        <label>Password<input name="password" type="password" autoComplete={signUp ? "new-password" : "current-password"} required minLength={signUp ? 8 : 1} maxLength={128} disabled={pending} /></label>
        {signUp && <p className="muted">Use 8–128 characters. We will email you a link to confirm the address.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <button className="button" disabled={pending}>{pending ? "Please wait…" : title}</button>
      </form>
      {!signUp && <p><Link href="/forgot-password"><a>Forgot your password?</a></Link></p>}
      <p>{signUp ? "Already have an account? " : "New to Roomly? "}<Link href={signUp ? "/sign-in" : "/sign-up"}><a>{signUp ? "Sign in" : "Create an account"}</a></Link></p>
    </>}
  </AuthPage>;
}
