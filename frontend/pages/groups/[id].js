import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";

import Field from "@/components/Field";
import Seats, { MAX_MEMBERS } from "@/components/Seats";
import SignInPrompt from "@/components/SignInPrompt";
import SprintNotice from "@/components/SprintNotice";
import { api } from "@/lib/api";
import { date } from "@/lib/format";
import { useSession } from "@/lib/useSession";

import styles from "@/styles/groups.module.css";

const INVITATION_STATE = {
  pending: { label: "Pending", badge: "badge-accent" },
  accepted: { label: "Joined", badge: "badge-good" },
  declined: { label: "Declined", badge: "" },
  expired: { label: "Expired", badge: "" },
};

export default function GroupPage() {
  const router = useRouter();
  const { id } = router.query;
  const { session, ready } = useSession();
  const [group, setGroup] = useState(null);
  const [sent, setSent] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const detail = await api.group(id);
      setGroup(detail);
      setSent(detail.my_role === "owner" ? await api.sentInvitations(id) : []);
      setError(null);
    } catch (err) {
      setError(err);
    }
  }, [id]);

  useEffect(() => {
    if (session && id) load();
  }, [session, id, load]);

  if (!ready) return <div className="container page" />;
  if (!session) {
    return (
      <div className="container page">
        <SignInPrompt what="open this group" />
      </div>
    );
  }
  if (error && !group) {
    return (
      <div className="container page">
        <div className="empty">
          <h3>{error.status === 404 || error.status === 403 ? "This group isn't available" : "Something went wrong"}</h3>
          <p>
            {error.status === 404 || error.status === 403
              ? "It may have been dissolved, or you're no longer a member."
              : error.message}
          </p>
          <Link href="/groups">
            <a className="btn btn-ghost">All groups</a>
          </Link>
        </div>
      </div>
    );
  }
  if (!group) {
    return (
      <div className="container page">
        <div className="skeleton" style={{ minHeight: 320 }} />
      </div>
    );
  }

  const owner = group.my_role === "owner";
  const full = group.members.length >= MAX_MEMBERS;

  return (
    <div className="container page">
      <Head>
        <title>{group.name} · Roomly</title>
      </Head>
      <Link href="/groups">
        <a className="btn btn-quiet" style={{ marginLeft: -10 }}>
          ← All groups
        </a>
      </Link>
      <div className={styles.header}>
        <div>
          <p className="eyebrow">{owner ? "You own this group" : "Member"}</p>
          <h1>{group.name}</h1>
          <div className="row">
            <Seats taken={group.members.length} />
            <span className="muted">
              {group.members.length} of {MAX_MEMBERS} · since {date(group.created_at)}
            </span>
          </div>
        </div>
      </div>

      {error ? (
        <div className="alert alert-error" role="alert" style={{ marginBottom: 20 }}>
          {error.message}
        </div>
      ) : null}

      <div className="split">
        <div className="stack">
          <section className="card" aria-label="Members">
            <h3>Members</h3>
            <ul className={styles.members}>
              {group.members.map((m) => (
                <Member
                  key={m.user.id ?? m.joined_at}
                  member={m}
                  me={m.user.id === session.user.id}
                  canManage={owner}
                  groupId={group.id}
                  onChanged={load}
                  onError={setError}
                />
              ))}
            </ul>
          </section>

          <SprintNotice
            sprint={5}
            compact
            title="The group room"
            items={[
              "Chat with emoji reactions, live for everyone in the group",
              "Polls on listings and shared comparisons; a closed poll stays closed",
              "Notifications for new messages, polls and listing changes",
            ]}
            endpoints={[`GET /groups/{id}/messages`, `POST /groups/{id}/polls`, `PUT /polls/{id}/vote`]}
          />
        </div>

        <aside className={styles.side}>
          {owner ? (
            <section className="card stack" aria-label="Invite">
              <h3>Invite someone</h3>
              {full ? (
                <p className="muted" style={{ margin: 0 }}>
                  The group is full. Six is the limit, so everyone can still agree on one place.
                </p>
              ) : (
                <InviteForm groupId={group.id} onSent={load} />
              )}
              {sent.length ? (
                <div>
                  <p className="label" style={{ margin: "8px 0" }}>
                    Sent invitations
                  </p>
                  {sent.map((inv) => (
                    <div key={inv.id} className={styles.inviteRow}>
                      <div>
                        <div>{inv.email}</div>
                        <div className="hint">
                          {inv.state === "pending" ? `Expires ${date(inv.expires_at)}` : date(inv.responded_at ?? inv.expires_at)}
                        </div>
                      </div>
                      <span className={`badge ${INVITATION_STATE[inv.state]?.badge ?? ""}`}>
                        {INVITATION_STATE[inv.state]?.label ?? inv.state}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}
          <LeaveGroup group={group} owner={owner} onLeft={() => router.push("/groups")} />
        </aside>
      </div>
    </div>
  );
}

function initials(name) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function Member({ member, me, canManage, groupId, onChanged, onError }) {
  const [confirm, setConfirm] = useState(null); // "remove" | "owner" | null
  const [busy, setBusy] = useState(false);

  async function act(kind) {
    setBusy(true);
    try {
      if (kind === "remove") await api.removeMember(groupId, member.user.id);
      else await api.transferOwnership(groupId, member.user.id);
      await onChanged();
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  }

  return (
    <li className={styles.member}>
      <span className={styles.avatar} aria-hidden="true">
        {initials(member.user.name)}
      </span>
      <div className={styles.memberInfo}>
        <div className={styles.memberName}>
          {member.user.name}
          {me ? <span className="muted"> (you)</span> : null}
        </div>
        <div className={styles.memberSub}>
          {member.role === "owner" ? "Owner" : "Member"} · joined {date(member.joined_at)}
        </div>
      </div>
      {canManage && !me ? (
        confirm ? (
          <div className="row" style={{ gap: 6 }}>
            <span className="hint">{confirm === "remove" ? "Remove from the group?" : "Hand over ownership?"}</span>
            <button className="btn btn-quiet" onClick={() => setConfirm(null)} disabled={busy}>
              Cancel
            </button>
            <button
              className={`btn ${confirm === "remove" ? "btn-danger" : "btn-primary"}`}
              onClick={() => act(confirm)}
              disabled={busy}
            >
              {confirm === "remove" ? "Remove" : "Make owner"}
            </button>
          </div>
        ) : (
          <div className="row" style={{ gap: 6 }}>
            <button className="btn btn-quiet" onClick={() => setConfirm("owner")}>
              Make owner
            </button>
            <button className="btn btn-quiet" onClick={() => setConfirm("remove")}>
              Remove
            </button>
          </div>
        )
      ) : null}
    </li>
  );
}

function InviteForm({ groupId, onSent }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState({ busy: false, error: null, sentTo: null });

  async function submit(e) {
    e.preventDefault();
    setState({ busy: true, error: null, sentTo: null });
    try {
      const invitation = await api.invite(groupId, email);
      setEmail("");
      setState({ busy: false, error: null, sentTo: invitation.email });
      onSent();
    } catch (err) {
      setState({ busy: false, error: err, sentTo: null });
    }
  }

  const err = state.error;
  return (
    <form className="stack" onSubmit={submit} noValidate>
      <Field
        id="invite-email"
        label="Email address"
        type="email"
        autoComplete="off"
        placeholder="roommate@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={err?.fields.email ?? (err ? err.message : undefined)}
        hint="They'll see it under Groups after signing in with this email. Invitations expire after 7 days."
      />
      <button className="btn btn-primary btn-block" disabled={state.busy || !email.trim()}>
        {state.busy ? "Sending…" : "Send invitation"}
      </button>
      {state.sentTo ? (
        <div className="alert alert-good" role="status">
          Invitation sent to {state.sentTo}.
        </div>
      ) : null}
    </form>
  );
}

function LeaveGroup({ group, owner, onLeft }) {
  const [confirming, setConfirming] = useState(false);
  const [state, setState] = useState({ busy: false, error: null });
  const alone = group.members.length === 1;

  async function leave() {
    setState({ busy: true, error: null });
    try {
      await api.leaveGroup(group.id);
      onLeft();
    } catch (err) {
      setState({ busy: false, error: err });
    }
  }

  const warning = owner
    ? alone
      ? "You're the only member: leaving dissolves the group."
      : "Make someone else the owner first, then you can leave."
    : "You can rejoin only with a new invitation.";

  return (
    <section className="card" aria-label="Leave group">
      <h3>Leave group</h3>
      <p className="muted">{warning}</p>
      {state.error ? (
        <div className="alert alert-error" role="alert" style={{ marginBottom: 12 }}>
          {state.error.message}
        </div>
      ) : null}
      {confirming ? (
        <div className="row" style={{ gap: 6 }}>
          <button className="btn btn-quiet" onClick={() => setConfirming(false)} disabled={state.busy}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={leave} disabled={state.busy}>
            {alone && owner ? "Dissolve and leave" : "Leave"}
          </button>
        </div>
      ) : (
        <button className="btn btn-ghost" onClick={() => setConfirming(true)} disabled={owner && !alone}>
          Leave {group.name}
        </button>
      )}
    </section>
  );
}
