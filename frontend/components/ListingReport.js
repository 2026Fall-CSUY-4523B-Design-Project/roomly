import Link from "next/link";
import { useState } from "react";

import { reportListing } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ListingReport({ listingId }) {
  const { user, loading, authenticatedRequest } = useAuth();
  const [reason, setReason] = useState("wrong_value");
  const [details, setDetails] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    if (status === "pending") return;
    setStatus("pending");
    setError("");
    try {
      await reportListing(authenticatedRequest, listingId, { reason, details: details.trim() || null });
      setStatus("success");
    } catch (err) {
      setError(err.status === 401 ? "Your session expired. Please sign in again." : err.message);
      setStatus("idle");
    }
  }

  return (
    <section className="card" aria-labelledby="report-heading">
      <h2 id="report-heading">Report incorrect data</h2>
      {loading ? <p role="status">Checking session…</p> : !user ? (
        <p><Link href="/sign-in"><a>Sign in</a></Link> to report incorrect data or a wrong merge.</p>
      ) : status === "success" ? (
        <p role="status">Report submitted. Thank you — it is awaiting review.</p>
      ) : (
        <form className="auth-form" onSubmit={submit}>
          <label>Reason
            <select value={reason} onChange={(e) => setReason(e.target.value)} disabled={status === "pending"}>
              <option value="wrong_value">Incorrect listing information</option>
              <option value="wrong_merge">Different listings merged together</option>
              <option value="unavailable">Listing is unavailable</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label>Details (optional)
            <textarea value={details} onChange={(e) => setDetails(e.target.value)} maxLength={2000} rows={4} disabled={status === "pending"} />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <div><button className="button" disabled={status === "pending"}>{status === "pending" ? "Submitting…" : "Submit report"}</button></div>
        </form>
      )}
    </section>
  );
}
