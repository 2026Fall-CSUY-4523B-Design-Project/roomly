import Link from "next/link";
import { useRouter } from "next/router";
import GroupWorkspace, { Feedback, shortDate, useGroupData } from "@/components/GroupWorkspace";

const MAX_MEMBERS = 6;
const load = request => Promise.all([request("/groups"), request("/invitations")]);

function Directory() {
  const router = useRouter();
  const listing = Array.isArray(router.query.listing) ? router.query.listing[0] : router.query.listing;
  const state = useGroupData(load);
  const [groups, invitations] = state.data || [[], []];
  const roomLink = id => ({ pathname: "/groups/[id]", query: { id, ...(listing && { listing }) } });
  function respond(id, decision) {
    state.run(async request => {
      await request(`/invitations/${id}/${decision}`, { method: "POST" });
      state.refresh();
    });
  }
  return <>
    <header className="group-title">
      <h1>Groups</h1>
      <p className="muted">{listing ? "Pick a group to start a thread about this listing." : "Search, compare and decide together with up to five housemates."}</p>
    </header>
    <Feedback state={state} />
    {state.data && <fieldset disabled={state.pending}>
      {invitations.length > 0 && <section className="card group-invitations">
        <h2>Invitations for you</h2>
        <ul className="group-list">{invitations.map(inv => <li key={inv.id} className="group-incoming">
          <div><strong>{inv.group_name}</strong>
            <p className="muted">Invited by {inv.invited_by || "a member"} · Expires {shortDate(inv.expires_at)}</p></div>
          <span className="group-row-actions">
            <button type="button" className="button" onClick={() => respond(inv.id, "accept")}>Accept</button>
            <button type="button" className="button secondary" onClick={() => respond(inv.id, "decline")}>Decline</button>
          </span>
        </li>)}</ul>
      </section>}
      <section className="card">
        <h2>Your groups</h2>
        {groups.length === 0 ? <p className="muted">You haven’t joined a group yet. Create one below, or ask a friend to invite you.</p>
          : <ul className="group-list">{groups.map(group => <li key={group.id}>
            <Link href={roomLink(group.id)}><a className="group-link">
              <span><strong>{group.name}</strong>
                <span className="muted">{group.member_count} of {MAX_MEMBERS} members · Created {shortDate(group.created_at)}</span></span>
              {group.role === "owner" && <span className="tag">Owner</span>}
              <span aria-hidden="true" className="group-link-arrow">→</span>
            </a></Link>
          </li>)}</ul>}
        <form className="group-inline-form group-section-footer" onSubmit={event => {
          event.preventDefault();
          const name = event.currentTarget.elements.name.value.trim();
          if (!name) return;
          state.run(async request => {
            const group = await request("/groups", { method: "POST", body: { name } });
            await router.push(roomLink(group.id));
          });
        }}>
          <label className="visually-hidden" htmlFor="group-name">Group name</label>
          <input id="group-name" name="name" required maxLength={80} placeholder="Name a new group, e.g. Bushwick crew" />
          <button className="button">Create group</button>
        </form>
      </section>
    </fieldset>}
  </>;
}

export default function Groups() {
  return <GroupWorkspace>{user => <Directory key={user.id} />}</GroupWorkspace>;
}
