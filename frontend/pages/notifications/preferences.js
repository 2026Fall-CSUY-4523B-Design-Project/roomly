import { useState } from "react";
import AccountWorkspace from "@/components/AccountWorkspace";
import { Feedback, useGroupData } from "@/components/GroupWorkspace";

const path = "/me/notification-settings";
const load = request => request(path);
const kinds = { new_match: "New saved-search matches", price_change: "Price changes", removed: "Listing removals", message: "Group messages" };

function Preferences() {
  const state = useGroupData(load);
  const settings = state.data;
  const [saved, setSaved] = useState(false);
  const [problem, setProblem] = useState("");
  function submit(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const body = {
      kinds: data.getAll("kind"), email: data.has("email"), digest: data.has("digest"),
      quiet_start: data.get("start") || null, quiet_end: data.get("end") || null,
    };
    setSaved(false);
    if (!body.quiet_start !== !body.quiet_end) {
      setProblem("Quiet hours need both a start and an end time, or leave both empty.");
      return;
    }
    setProblem("");
    state.run(async request => {
      state.update(await request(path, { method: "PUT", body }));
      setSaved(true);
    });
  }
  return <><Feedback state={state} />
    {settings && <form className="card notification-settings" onSubmit={submit} onChange={() => { setSaved(false); setProblem(""); }}>
      <fieldset disabled={state.pending}><legend>Alert types</legend>
        {Object.entries(kinds).map(([value, label]) => <label key={value}><input type="checkbox" name="kind" value={value} defaultChecked={settings.kinds.includes(value)} /> {label}</label>)}
      </fieldset>
      <fieldset disabled={state.pending}><legend>Delivery preferences</legend>
        <label><input type="checkbox" name="email" defaultChecked={settings.email} /> Email alerts</label>
        <label><input type="checkbox" name="digest" defaultChecked={settings.digest} /> Digest</label>
        <p className="muted field-note">Email and digest delivery are coming soon. Your choices are saved now and take effect when they launch.</p>
      </fieldset>
      <fieldset disabled={state.pending}><legend>Quiet hours</legend>
        <p className="muted field-note">Alert emails hold off during these local times. Set both, or leave both empty.</p>
        <div className="quiet-hours">
          <label>From <input type="time" step="any" name="start" defaultValue={settings.quiet_start || ""} /></label>
          <label>Until <input type="time" step="any" name="end" defaultValue={settings.quiet_end || ""} /></label>
        </div>
      </fieldset>
      {problem && <p role="alert" className="error">{problem}</p>}
      <div className="form-actions">
        <button className="button" disabled={state.pending}>{state.pending ? "Saving…" : "Save preferences"}</button>
        <span role="status" className="muted">{saved ? "Preferences saved." : ""}</span>
      </div>
    </form>}
  </>;
}
export default function Settings() {
  return <AccountWorkspace title="Notification preferences" back={{ href: "/notifications", label: "Inbox" }}>{user => <Preferences key={user.id} />}</AccountWorkspace>;
}
