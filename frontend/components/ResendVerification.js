import { useState } from "react";

import { resendVerification } from "@/lib/api";

// Asks for a new confirmation link. The server answers the same for every address, so the
// confirmation here says "if" and never "we sent".
export default function ResendVerification({ email }) {
  const [state, setState] = useState("idle");
  async function resend() {
    setState("pending");
    try {
      await resendVerification(email);
      setState("done");
    } catch {
      setState("failed");
    }
  }
  return <>
    <button type="button" className="button secondary" onClick={resend} disabled={state === "pending" || state === "done"}>
      {state === "pending" ? "Sending…" : "Send the link again"}
    </button>
    {state === "done" && <p className="muted" role="status">If {email} still needs confirming, a new link is on its way. It can take a minute; links can be requested once a minute.</p>}
    {state === "failed" && <p className="error" role="alert">Could not send the link. Please try again.</p>}
  </>;
}
