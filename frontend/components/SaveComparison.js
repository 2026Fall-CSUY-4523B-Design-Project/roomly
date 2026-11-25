import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

export default function SaveComparison({ ids }) {
  const { user, loading, authenticatedRequest } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  if (loading) return null;
  if (!user) return <Link href="/sign-in?next=/compare"><a className="button secondary">Sign in to save</a></Link>;
  async function save(event) {
    event.preventDefault();
    const title = event.currentTarget.elements.title.value.trim();
    setPending(true);
    setError("");
    try {
      const saved = await authenticatedRequest("/comparisons", { method: "POST", body: { title: title || null, listing_ids: ids } });
      await router.push("/comparisons/" + saved.id);
    } catch (err) {
      // Only reset on failure: on success this form unmounts with the navigation.
      setError(err.message);
      setPending(false);
    }
  }
  return <form className="save-comparison" onSubmit={save}>
    <input name="title" maxLength={120} placeholder="Title (optional)" aria-label="Comparison title (optional)" />
    <button className="button" disabled={pending}>{pending ? "Saving…" : "Save"}</button>
    {error && <p role="alert" className="error">{error}</p>}
  </form>;
}
