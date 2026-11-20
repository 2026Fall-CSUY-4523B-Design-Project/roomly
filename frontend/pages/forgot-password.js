import Link from "next/link";
import { useState } from "react";

import AuthPage from "@/components/AuthPage";
import { forgotPassword } from "@/lib/api";

export default function ForgotPassword() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [sentTo, setSentTo] = useState("");

  async function submit(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    const email = new FormData(event.currentTarget).get("email").trim();
    try {
      await forgotPassword(email);
      setSentTo(email);
    } catch (err) {
      setError(err.message || "Could not connect. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return <AuthPage title="Reset your password">
    {sentTo ? <>
      {/* The same words for every address: the server does not say whether an account exists. */}
      <p role="status">If an account exists for <strong>{sentTo}</strong>, we emailed a link to choose a new password. It works once and expires in 30 minutes.</p>
      <p><Link href="/sign-in"><a>Back to sign in</a></Link></p>
    </> : <form onSubmit={submit} className="auth-form">
      <p className="muted">Enter the email you signed up with and we will send you a reset link.</p>
      <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254} disabled={pending} /></label>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="button" disabled={pending}>{pending ? "Please wait…" : "Send reset link"}</button>
      <p><Link href="/sign-in"><a>Back to sign in</a></Link></p>
    </form>}
  </AuthPage>;
}
