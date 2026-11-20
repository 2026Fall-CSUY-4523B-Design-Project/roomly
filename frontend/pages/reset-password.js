import Link from "next/link";
import { useState } from "react";

import AuthPage from "@/components/AuthPage";
import { resetPassword } from "@/lib/api";
import { useUrlToken } from "@/lib/token";

export default function ResetPassword() {
  const { ready, token } = useUrlToken();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (data.get("password") !== data.get("confirm")) {
      setError("The two passwords do not match.");
      return;
    }
    setPending(true);
    setError("");
    try {
      await resetPassword(token, data.get("password"));
      setDone(true);
    } catch (err) {
      if (err.code === "invalid_token") setInvalid(true);
      else setError(err.message || "Could not connect. Please try again.");
    } finally {
      setPending(false);
    }
  }

  let body;
  if (!ready) body = <p role="status">Loading…</p>;
  else if (done) body = <>
    <p role="status">Your password is changed and every device is signed out. Sign in with the new password.</p>
    <Link href="/sign-in"><a className="button">Sign in</a></Link>
  </>;
  else if (!token || invalid) body = <>
    <p className="error" role="alert">This reset link is invalid or has expired.</p>
    <p><Link href="/forgot-password"><a>Request a new link</a></Link></p>
  </>;
  else body = <form onSubmit={submit} className="auth-form">
    <label>New password<input name="password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} disabled={pending} /></label>
    <label>Repeat it<input name="confirm" type="password" autoComplete="new-password" required minLength={8} maxLength={128} disabled={pending} /></label>
    <p className="muted">Use 8–128 characters. Changing it signs you out everywhere.</p>
    {error && <p className="error" role="alert">{error}</p>}
    <button className="button" disabled={pending}>{pending ? "Please wait…" : "Change password"}</button>
  </form>;

  return <AuthPage title="Choose a new password" noReferrer>{body}</AuthPage>;
}
