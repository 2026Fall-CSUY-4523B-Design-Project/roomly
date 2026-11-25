import Link from "next/link";
import { useCallback, useState } from "react";
import AccountWorkspace from "@/components/AccountWorkspace";
import { Feedback, When, useGroupData } from "@/components/GroupWorkspace";
import { useAuth } from "@/lib/auth";

const PAGE_SIZE = 20;
function Inbox() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const load = useCallback(request => request(`/notifications?unread=${unreadOnly}&offset=${offset}&limit=${PAGE_SIZE}`), [unreadOnly, offset]);
  const state = useGroupData(load);
  const { authenticatedRequest } = useAuth();
  const page = state.data;
  function markRead(id) {
    state.run(async request => {
      const result = await request(id ? "/notifications/" + id + "/read" : "/notifications/read-all", { method: "POST" });
      if (id && !unreadOnly) {
        // The item stays in this view, so patch it in place instead of refetching the page.
        state.update(current => current && { ...current, unread: Math.max(0, current.unread - 1),
          items: current.items.map(item => item.id === id ? result : item) });
      } else if (unreadOnly && offset) setOffset(0);
      else state.refresh();
    });
  }
  // Following a notification's link counts as reading it; the page unmounts, so nothing to update.
  const opened = item => () => {
    if (!item.read) authenticatedRequest("/notifications/" + item.id + "/read", { method: "POST" }).catch(() => {});
  };
  return <section className="card"><div className="group-section-head">
      <h2>Inbox {page && page.unread > 0 && <span className="inbox-count">{page.unread} unread</span>}</h2>
      <div className="inbox-controls">
        <label><input type="checkbox" checked={unreadOnly} disabled={state.pending}
          onChange={event => { setOffset(0); setUnreadOnly(event.target.checked); }} /> Unread only</label>
        {page && page.unread > 0 && <button type="button" className="link-button" disabled={state.pending} onClick={() => markRead()}>Mark all as read</button>}
      </div>
    </div><Feedback state={state} />
    {page && <>
      {page.items.length ? <ul className="group-list">{page.items.map(item => <li className={"inbox-item" + (item.read ? "" : " unread")} key={item.id}>
        <div className="inbox-line">
          <span className="inbox-title">{item.title}</span>
          <When value={item.created_at} />
        </div>
        <div className="inbox-actions">
          {item.group_id && <Link href={{ pathname: "/groups/[id]", query: { id: item.group_id, ...(item.listing_id && { listing: item.listing_id }) } }}>
            <a onClick={opened(item)}>Open group</a></Link>}
          {item.listing_id && <Link href={"/listings/" + item.listing_id}><a onClick={opened(item)}>View listing</a></Link>}
          {!item.read && <button type="button" className="link-button" disabled={state.pending} onClick={() => markRead(item.id)}>Mark as read</button>}
        </div>
      </li>)}</ul> : <p className="muted account-empty-line">{unreadOnly ? "You’re all caught up." : "No notifications yet. Price changes, new matches and group messages will show up here."}</p>}
      {(offset > 0 || offset + page.limit < page.total) && <nav className="inbox-pages" aria-label="Inbox pages">
        <button type="button" className="button secondary" disabled={state.pending || offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)}>Previous</button>
        <span className="muted">{offset + 1}–{Math.min(offset + page.limit, page.total)} of {page.total}</span>
        <button type="button" className="button secondary" disabled={state.pending || offset + page.limit >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
      </nav>}
    </>}</section>;
}
export default function Notifications() {
  return <AccountWorkspace title="Notifications"
    action={<Link href="/notifications/preferences"><a className="button secondary">Preferences</a></Link>}>{user => <Inbox key={user.id} />}</AccountWorkspace>;
}
