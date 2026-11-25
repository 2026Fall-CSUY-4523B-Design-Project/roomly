import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

// Inline "send this to one of my groups" control, shared by listing detail and /compare.
// `onConfirm(request, groupId, extra)` does the work and returns the room URL to open.
export default function GroupPicker({ label, confirmLabel, onConfirm, withTitle = false, defaultTitle = "", skipIfSingle = false }) {
  const { user, authenticatedRequest } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [groups, setGroups] = useState(null);
  const [groupId, setGroupId] = useState("");
  const [title, setTitle] = useState(defaultTitle);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!open || groups) return;
    let active = true;
    authenticatedRequest("/groups").then(list => {
      if (!active) return;
      setGroups(list);
      setGroupId(list[0]?.id || "");
      if (skipIfSingle && list.length === 1) go(list[0].id);
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
    // go() only reads current props; listing it as a dependency would refetch on every render.
  }, [open, groups, authenticatedRequest]);

  if (!user || user.role === "admin") return null;

  async function go(id) {
    setPending(true);
    setError("");
    try {
      const href = await onConfirm(authenticatedRequest, id, { title: title.trim() || undefined });
      await router.push(href);
    } catch (err) {
      setError(err.message);
      setPending(false);
    }
  }

  if (!open) return <button type="button" className="button secondary" onClick={() => setOpen(true)}>{label}</button>;
  return <div className="group-picker" role="group" aria-label={label}>
    {error && <p role="alert" className="error">{error}</p>}
    {!groups && !error ? <p role="status" className="muted">Loading your groups…</p>
      : groups && !groups.length ? <p>You’re not in a group yet. <Link href="/groups"><a>Create one</a></Link> first.</p>
      : groups && <form onSubmit={event => { event.preventDefault(); go(groupId); }}>
        <fieldset disabled={pending}>
          <label>Group <select value={groupId} onChange={event => setGroupId(event.target.value)}>
            {groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}
          </select></label>
          {withTitle && <label><span>Title <span className="muted">(optional)</span></span>
            <input value={title} maxLength={120} onChange={event => setTitle(event.target.value)} placeholder="e.g. Top three for Saturday" /></label>}
          <div className="group-picker-actions">
            <button className="button">{pending ? "Opening…" : confirmLabel}</button>
            <button type="button" className="button secondary" onClick={() => { setOpen(false); setError(""); }}>Cancel</button>
          </div>
        </fieldset>
      </form>}
  </div>;
}
