import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";

import Field from "@/components/Field";
import Seats, { MAX_MEMBERS } from "@/components/Seats";
import SignInPrompt from "@/components/SignInPrompt";
import { api } from "@/lib/api";
import { date, plural } from "@/lib/format";
import { useSession } from "@/lib/useSession";

import styles from "@/styles/groups.module.css";

// Group Management (§8.1.2.2): your groups, invitations waiting for you, and a new group.
export default function GroupsPage() {
  const { session, ready } = useSession();
  const router = useRouter();
  const [data, setData] = useState({ groups: null, invitations: null, error: null });

  const load = useCallback(async () => {
    try {
      const [groups, invitations] = await Promise.all([api.groups(), api.invitations()]);
      setData({ groups, invitations, error: null });
    } catch (err) {
      setData((d) => ({ ...d, error: err }));
    }
  }, []);

  useEffect(() => {
    if (session) load();
  }, [session, load]);

  if (!ready) return <div className="container page" />;
  if (!session) {
    return (
      <div className="container page">
        <SignInPrompt what="see your groups" />
      </div>
    );
  }
  const isAdmin = session.user.role === "admin";

  return (
    <div className="container page">
      <Head>
        <title>Groups · Roomly</title>
      </Head>
      <div className={styles.header}>
        <div>
          <p className="eyebrow">Group management</p>
          <h1>Your groups</h1>
          <p className="lede">Up to six people search together, compare shortlists and vote in a shared room.</p>
        </div>
      </div>

      {data.error ? (
        <div className="alert alert-error" role="alert" style={{ marginBottom: 20 }}>
          {data.error.message}
        </div>
      ) : null}

      <div className="split">
        <section aria-label="Your groups">
          {data.groups === null ? (
            <div className="grid-cards">
              <div className="skeleton" />
              <div className="skeleton" />
            </div>
          ) : data.groups.length === 0 ? (
            <div className="empty">
              <h3>No groups yet</h3>
              <p>Create one and invite your roommates by email, or accept an invitation you received.</p>
            </div>
          ) : (
            <div className="grid-cards">
              {data.groups.map((g) => (
                <GroupCard key={g.id} group={g} />
              ))}
            </div>
          )}
        </section>

        <aside className={styles.side}>
          {data.invitations?.length ? (
            <Invitations
              invitations={data.invitations}
              onAccepted={(group) => router.push(`/groups/${group.id}`)}
              onChanged={load}
            />
          ) : null}
          {isAdmin ? (
            <div className="alert alert-info">
              Administrators review data and can&rsquo;t join groups, so their accounts stay neutral.
            </div>
          ) : (
            <CreateGroup onCreated={(group) => router.push(`/groups/${group.id}`)} />
          )}
        </aside>
      </div>
    </div>
  );
}

function GroupCard({ group }) {
  return (
    <Link href={`/groups/${group.id}`}>
      <a className={`card card-link ${styles.groupCard}`}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className={styles.groupName}>{group.name}</h2>
          {group.role === "owner" ? <span className="badge badge-accent">Owner</span> : null}
        </div>
        <Seats taken={group.member_count} />
        <div className={styles.meta}>
          <span>
            {group.member_count} of {MAX_MEMBERS} members
          </span>
          <span>Since {date(group.created_at)}</span>
        </div>
      </a>
    </Link>
  );
}

function Invitations({ invitations, onAccepted, onChanged }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  async function respond(invitation, accept) {
    setBusy(invitation.id);
    setError(null);
    try {
      if (accept) onAccepted(await api.acceptInvitation(invitation.id));
      else await api.declineInvitation(invitation.id);
      onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card" aria-label="Invitations for you">
      <h3>{plural(invitations.length, "invitation")} for you</h3>
      {error ? (
        <div className="alert alert-error" role="alert" style={{ margin: "10px 0" }}>
          {error.message}
        </div>
      ) : null}
      {invitations.map((inv) => (
        <div key={inv.id} className={styles.inviteRow}>
          <div>
            <div style={{ fontWeight: 600 }}>{inv.group_name}</div>
            <div className="hint">
              {inv.invited_by ? `From ${inv.invited_by} · ` : ""}expires {date(inv.expires_at)}
            </div>
          </div>
          <div className="row" style={{ gap: 6 }}>
            <button className="btn btn-quiet" disabled={busy === inv.id} onClick={() => respond(inv, false)}>
              Decline
            </button>
            <button className="btn btn-primary" disabled={busy === inv.id} onClick={() => respond(inv, true)}>
              Join
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}

function CreateGroup({ onCreated }) {
  const [name, setName] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onCreated(await api.createGroup(name));
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <form className="card stack" onSubmit={submit} noValidate>
      <h3>Start a group</h3>
      <p className="muted" style={{ margin: 0 }}>
        You&rsquo;ll be its owner. Invite up to five others next.
      </p>
      <Field
        id="group-name"
        label="Group name"
        placeholder="e.g. Bushwick crew"
        maxLength={80}
        value={name}
        onChange={(e) => setName(e.target.value)}
        error={error?.fields.name ?? (error && !Object.keys(error.fields).length ? error.message : undefined)}
      />
      <button className="btn btn-primary btn-block" disabled={busy || !name.trim()}>
        {busy ? "Creating…" : "Create group"}
      </button>
    </form>
  );
}
