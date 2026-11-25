import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback } from "react";
import GroupWorkspace, { Avatar, Feedback, shortDate, useGroupData } from "@/components/GroupWorkspace";
import GroupRoom, { Polls } from "@/components/GroupRoom";

const MAX_MEMBERS = 6;
const STATE_TAGS = { pending: "", accepted: " ok", declined: " muted-tag", expired: " muted-tag", revoked: " muted-tag" };

function Group({ id, user, listing, comparison }) {
  const router = useRouter();
  const path = "/groups/" + encodeURIComponent(id);
  const load = useCallback(request => Promise.all([request(path), request(path + "/invitations"), request(path + "/comparisons")]), [path]);
  const state = useGroupData(load);
  const [group, invitations, comparisons] = state.data || [];
  const owner = group?.my_role === "owner";
  function change(suffix, body, method = "POST", form) {
    state.run(async request => {
      await request(path + suffix, { method, body });
      if (form) form.reset();
      if (suffix === "/leave") await router.replace("/groups");
      else state.refresh();
    });
  }
  const full = group && group.members.length >= MAX_MEMBERS;
  return <>
    <Link href="/groups"><a className="back-link">← All groups</a></Link>
    {group ? <header className="group-title">
      <h1>{group.name}</h1>
      <p className="muted">{group.members.length} of {MAX_MEMBERS} members · {owner ? "You own this group" : "Member"} · Created {shortDate(group.created_at)}</p>
    </header> : null}
    <Feedback state={state} />
    {group && <div className="group-layout">
      <div className="group-main">
        <GroupRoom path={path} comparisons={comparisons} listing={listing} comparison={comparison} />
      </div>
      <aside className="group-side">
        <fieldset disabled={state.pending}>
          <section className="card">
            <h2>Members</h2>
            <ul className="group-list">{group.members.map(({ user: member, role }) => <li key={member.id} className="group-member">
              <Avatar name={member.name} />
              <span className="group-member-name">{member.name}{member.id === user.id && <span className="muted"> (you)</span>}</span>
              {role === "owner" && <span className="tag">Owner</span>}
              {owner && member.id !== user.id && <span className="group-member-actions">
                <button type="button" className="link-button" onClick={() => window.confirm(`Make ${member.name} the owner? You'll become a regular member.`) && change("/transfer", { user_id: member.id })}>Make owner</button>
                <button type="button" className="link-button danger" onClick={() => window.confirm(`Remove ${member.name} from this group?`) && change("/members/" + member.id, undefined, "DELETE")}>Remove</button>
              </span>}
            </li>)}</ul>
            <div className="group-section-footer">
              {owner && group.members.length > 1
                ? <p className="muted">To leave, make someone else the owner first.</p>
                : <button type="button" className="link-button danger" onClick={() => window.confirm(owner ? "Dissolve this group? Its messages, polls and shared comparisons will be deleted." : "Leave this group?") && change("/leave")}>{owner ? "Dissolve group" : "Leave group"}</button>}
            </div>
          </section>
          <section className="card">
            <h2>Invitations</h2>
            {owner && <form className="group-inline-form" onSubmit={event => { event.preventDefault(); const form = event.currentTarget; change("/invitations", { email: form.elements.email.value.trim() }, "POST", form); }}>
              <label className="visually-hidden" htmlFor="invite-email">Email address</label>
              <input id="invite-email" name="email" type="email" required placeholder="name@example.com" disabled={full} />
              <button className="button" disabled={full}>Invite</button>
            </form>}
            {owner && full && <p className="muted">This group is full.</p>}
            {invitations.length ? <ul className="group-list">{invitations.map(inv => <li key={inv.id} className="group-invite">
              <span className="group-invite-email">{inv.email}</span>
              <span className={"tag" + (STATE_TAGS[inv.state] ?? "")}>{inv.state[0].toUpperCase() + inv.state.slice(1)}</span>
            </li>)}</ul> : <p className="muted">No invitations sent yet.</p>}
          </section>
        </fieldset>
        <Polls path={path} user={user} owner={owner} />
      </aside>
    </div>}
  </>;
}

export default function GroupPage() {
  const router = useRouter();
  const first = value => Array.isArray(value) ? value[0] : value;
  const id = first(router.query.id);
  const listing = first(router.query.listing);
  const comparison = first(router.query.comparison);
  return <GroupWorkspace title="Group room" wide>{user => id && <Group key={[user.id, id, listing, comparison].join("/")} id={id} user={user} listing={listing} comparison={comparison} />}</GroupWorkspace>;
}
