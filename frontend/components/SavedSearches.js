import { useState } from "react";
import { Feedback, useGroupData } from "@/components/GroupWorkspace";

const load = request => request("/saved-searches");
export default function SavedSearches({ criteria, onOpen, onDelete }) {
  const state = useGroupData(load);
  const [notice, setNotice] = useState("");
  function save(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    state.run(async request => {
      setNotice("");
      const saved = await request("/saved-searches", { method: "POST", body: {
        name: data.get("name").trim(), criteria, alerts_enabled: data.has("alerts"),
      } });
      form.reset();
      setNotice("Saved " + saved.name + ".");
      state.refresh();
    });
  }
  function remove(item) {
    if (!window.confirm('Delete saved search “' + item.name + '”?')) return;
    state.run(async request => {
      await request("/saved-searches/" + item.id, { method: "DELETE" });
      onDelete(item.id);
      setNotice("Deleted " + item.name + ".");
      state.refresh();
    });
  }
  return <section className="card saved-searches"><h2>Saved searches</h2><Feedback state={state} />
    {state.data && <fieldset disabled={state.pending}>
      <form onSubmit={save}><label>Search name<input name="name" required maxLength={80} /></label>
        <label className="check"><input type="checkbox" name="alerts" defaultChecked />Enable match alerts</label>
        <button className="button">Save applied filters</button>
      </form>
      {state.data.length ? <ul>{state.data.map(item => <li key={item.id}>
        <button className="link-button" onClick={() => onOpen(item)}>{item.name}</button>
        <small>Match alerts {item.alerts_enabled ? "on" : "off"}</small>
        <button className="link-button" aria-label={"Delete " + item.name} onClick={() => remove(item)}>Delete</button>
      </li>)}</ul> : <p>No saved searches yet.</p>}
    </fieldset>}
    {notice && <p role="status">{notice}</p>}
  </section>;
}
