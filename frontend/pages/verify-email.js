import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import AuthPage from "@/components/AuthPage";
import { verifyEmail } from "@/lib/api";
import { useUrlToken } from "@/lib/token";

// Opened from the emailed link. The token is single-use, so the call happens once per page load.
export default function VerifyEmail() {
  const { ready, token } = useUrlToken();
  const started = useRef(false);
  const [state, setState] = useState({ status: "checking", message: "" });

  useEffect(() => {
    if (!ready || started.current) return;
    started.current = true;
    if (!token) {
      setState({ status: "failed", message: "This link is incomplete. Open it again from the email, or request a new one." });
      return;
    }
    verifyEmail(token)
      .then(() => setState({ status: "done", message: "" }))
      .catch((err) => setState({ status: "failed", message: err.message || "Could not confirm your email. Please try again." }));
  }, [ready, token]);

  return <AuthPage title="Confirm your email" noReferrer>
    {state.status === "checking" && <p role="status">Confirming your email…</p>}
    {state.status === "done" && <>
      <p role="status">Your email is confirmed. You can sign in now.</p>
      <Link href="/sign-in"><a className="button">Sign in</a></Link>
    </>}
    {state.status === "failed" && <>
      <p className="error" role="alert">{state.message}</p>
      <p>Sign in with your password to get a new confirmation link. <Link href="/sign-in"><a>Sign in</a></Link></p>
    </>}
  </AuthPage>;
}
