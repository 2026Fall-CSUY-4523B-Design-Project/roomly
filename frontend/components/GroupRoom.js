import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Avatar, Feedback, When, useGroupData } from "@/components/GroupWorkspace";
import { getListing } from "@/lib/api";
import { comparisonTitle } from "@/lib/comparison";
import { UNKNOWN, formatListingValue } from "@/lib/format";

const PAGE = 20;
const DEFAULT_REACTIONS = ["👍", "❤️", "🎉"];
const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`;

function SharedComparison({ id }) {
  const load = useCallback(request => request("/comparisons/" + id), [id]);
  const state = useGroupData(load);
  const comparison = state.data;
  if (!comparison) return <Feedback state={state} />;
  const { listings, rows, notes } = comparison.table;
  const titleOf = listingId => {
    const listing = listings.find(item => item.id === listingId);
    return listing ? comparisonTitle(listing) : "A listing";
  };
  const changes = comparison.changes.filter(change => change.state !== "unchanged");
  return <div className="group-comparison"><Feedback state={state} />
    <details className="group-comparison-details">
    <summary><strong>{comparison.title || "Shared comparison"}</strong> <span className="muted">· {listings.length} listings · saved by {comparison.saved_by.name}</span></summary>
    {changes.length > 0 && <ul className="group-changes" aria-label="Changes since this comparison was saved">{changes.map(change => <li key={change.listing_id}>
      <strong>{titleOf(change.listing_id)}</strong> {change.state === "removed" ? "is no longer available"
        : "changed" + (change.changed_fields.length ? ": " + change.changed_fields.join(", ").replace(/_/g, " ") : "")}
    </li>)}</ul>}
    <div className="comparison-table-wrap" role="region" aria-label="Shared comparison table" tabIndex={0}>
      <table className="comparison-table"><caption className="visually-hidden">{comparison.title || "Shared comparison"}. Cells marked Best have the best value in their row.</caption>
        <thead><tr><th scope="col">Attribute</th>{listings.map(item => <th scope="col" key={item.id}>
          <Link href={"/listings/" + item.id}><a>{comparisonTitle(item)}</a></Link></th>)}</tr></thead>
        <tbody>{rows.map(row => <tr key={row.key}>
          <th scope="row">{row.label}{row.direction && <span className="comparison-hint">{row.direction === "lower" ? "Lower" : "Higher"} is better</span>}</th>
          {listings.map(item => {
            const cell = row.cells.find(entry => entry.listing_id === item.id);
            const known = cell?.known && cell.value != null;
            const best = known && cell.best;
            return <td key={item.id} className={best ? "comparison-best" : undefined}>
              {known ? formatListingValue(row.key, cell.value) : UNKNOWN}
              {best && <span className="comparison-best-label">Best</span>}
            </td>;
          })}</tr>)}</tbody>
      </table>
    </div>
    {notes.map((note, index) => <p className="muted" key={index}>{note}</p>)}
    </details>
  </div>;
}

function Reactions({ message, onReact }) {
  const emojis = [...new Set([...DEFAULT_REACTIONS, ...message.reactions.map(item => item.emoji)])];
  return <div className="group-reactions">{emojis.map(emoji => {
    const reaction = message.reactions.find(item => item.emoji === emoji);
    const count = reaction?.count || 0;
    return <button type="button" key={emoji} className={"reaction" + (count ? "" : " empty")}
      aria-label={`React ${emoji}, ${plural(count, "reaction")}`} aria-pressed={!!reaction?.mine}
      onClick={() => onReact(emoji, reaction)}>{emoji}{count > 0 && <span>{count}</span>}</button>;
  })}</div>;
}

function Discussion({ path, thread, about, selectThread }) {
  const [field, id] = thread.split(":");
  const params = new URLSearchParams({ limit: String(PAGE) });
  if (id) params.set(field, id);
  const url = path + "/messages?" + params;
  const load = useCallback(request => request(url), [url]);
  const state = useGroupData(load);
  const [older, setOlder] = useState([]);
  const [ended, setEnded] = useState(false);
  const [body, setBody] = useState("");
  const latest = state.data || [];
  const messages = [...latest, ...older.filter(item => !latest.some(m => m.id === item.id))];
  const hasMore = !ended && (older.length ? true : latest.length >= PAGE);
  function refresh() {
    setOlder([]);
    setEnded(false);
    state.refresh();
  }
  function send() {
    const text = body.trim();
    if (!text) return;
    state.run(async request => {
      await request(path + "/messages", { method: "POST", body: { body: text, ...(id && { [field]: id }) } });
      setBody(""); refresh();
    });
  }
  function react(message, emoji, reaction) {
    state.run(async request => {
      const reactions = await request("/messages/" + message.id + "/reaction", reaction?.mine ? { method: "DELETE" } : { method: "PUT", body: { emoji } });
      const patch = items => items && items.map(item => item.id === message.id ? { ...item, reactions } : item);
      state.update(patch);
      setOlder(patch);
    });
  }
  return <><Feedback state={state} />{state.data && <fieldset disabled={state.pending}>
    <form className="group-composer" onSubmit={event => { event.preventDefault(); send(); }}>
      <label className="visually-hidden" htmlFor="message-body">Message</label>
      <textarea id="message-body" rows={3} required maxLength={4000} value={body} placeholder={about ? `Write about ${about}…` : "Write a message to the group…"}
        onChange={event => setBody(event.target.value)}
        onKeyDown={event => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); send(); } }} />
      <div className="group-composer-bar">
        <span className="group-composer-to">{about ? <>Posting about <strong>{about}</strong></> : "Posting to the whole group"}</span>
        <button className="button" disabled={!body.trim()} title="Send (⌘/Ctrl + Enter)">Send</button>
      </div>
    </form>
    <div className="group-feed-bar">
      <span className="muted">{messages.length ? "Newest first" : ""}</span>
      <button type="button" className="link-button" onClick={refresh}>Refresh</button>
    </div>
    {!messages.length && <p className="group-placeholder">{about ? <>No messages about <strong>{about}</strong> yet. Start the thread above.</> : "No messages yet. Start the conversation."}</p>}
    <ol className="group-feed">{messages.map(message => <li key={message.id} className="group-message">
      <Avatar name={message.author.name} />
      <div className="group-message-content">
        <div className="group-message-meta"><strong>{message.author.name}</strong> <span className="muted"><When value={message.sent_at} /></span>
          {!id && (message.listing_id || message.comparison_id) && <button type="button" className="tag tag-button"
            onClick={() => selectThread(message.listing_id ? "listing_id:" + message.listing_id : "comparison_id:" + message.comparison_id)}>
            {message.listing_id ? "Listing thread" : "Comparison thread"} →</button>}
        </div>
        <p className="group-message-body">{message.body}</p>
        <Reactions message={message} onReact={(emoji, reaction) => react(message, emoji, reaction)} />
      </div>
    </li>)}</ol>
    {hasMore && messages.length > 0 && <div className="group-more"><button type="button" className="button secondary" onClick={() => state.run(async request => {
      const page = await request(url + "&before=" + encodeURIComponent(messages[messages.length - 1].sent_at));
      setOlder(items => [...items, ...page]); setEnded(page.length < PAGE);
    })}>Load older messages</button></div>}
  </fieldset>}</>;
}

export function Polls({ path, user, owner }) {
  const load = useCallback(request => request(path + "/polls"), [path]);
  const state = useGroupData(load);
  const [composing, setComposing] = useState(false);
  function update(url, method, body) {
    state.run(async request => {
      const poll = await request(url, { method, body });
      state.update(items => items && items.map(item => item.id === poll.id ? poll : item));
    });
  }
  const polls = state.data || [];
  return <section className="card"><div className="group-section-head"><h2>Polls</h2>
    <button type="button" className="link-button" onClick={state.refresh}>Refresh</button></div>
    <Feedback state={state} />
    {state.data && <fieldset disabled={state.pending}>
      {!polls.length && !composing && <p className="muted">No polls yet. Ask the group to vote on tours, budgets or neighborhoods.</p>}
      {polls.map(poll => {
        const open = poll.state === "open";
        return <article key={poll.id} className={"group-poll" + (open ? "" : " closed")}>
          <h3>{poll.question}</h3>
          <ul className="group-poll-options">{poll.options.map(option => {
            const pct = poll.total_votes ? Math.round(option.votes / poll.total_votes * 100) : 0;
            const mine = poll.my_vote === option.id;
            return <li key={option.id}><button type="button" className={"poll-option" + (mine ? " mine" : "")} style={{ "--pct": pct + "%" }}
              disabled={!open} aria-pressed={mine} onClick={() => !mine && update("/polls/" + poll.id + "/vote", "PUT", { option_id: option.id })}>
              <span className="poll-option-text">{mine && <span aria-hidden="true">✓ </span>}{option.text}</span>
              <span className="poll-option-count">{option.votes} · {pct}%</span>
            </button></li>;
          })}</ul>
          <p className="muted group-poll-meta">{open ? "Open" : "Closed"} · {plural(poll.total_votes, "vote")}
            {open && (owner || poll.created_by === user.id) && <> · <button type="button" className="link-button"
              onClick={() => window.confirm("Close this poll? Members will no longer be able to vote.") && update("/polls/" + poll.id + "/close", "POST")}>Close poll</button></>}
          </p>
        </article>;
      })}
      {composing ? <form className="group-poll-form" onSubmit={event => {
        event.preventDefault();
        const form = event.currentTarget;
        const values = new FormData(form);
        const options = values.getAll("option").map(value => value.trim()).filter(Boolean);
        if (new Set(options.map(value => value.toLowerCase())).size !== options.length) {
          window.alert("Poll options must be different from each other.");
          return;
        }
        state.run(async request => {
          await request(path + "/polls", { method: "POST", body: { question: values.get("question").trim(), options } });
          setComposing(false);
          state.refresh();
        });
      }}>
        <label>Question <input name="question" required maxLength={200} placeholder="Which one do we tour first?" autoFocus /></label>
        <fieldset className="group-poll-choices"><legend>Options</legend>
          {[1, 2, 3, 4].map(n => <input key={n} name="option" aria-label={`Option ${n}${n > 2 ? " (optional)" : ""}`}
            placeholder={n > 2 ? `Option ${n} (optional)` : `Option ${n}`} required={n < 3} maxLength={120} />)}
        </fieldset>
        <div className="group-row-actions">
          <button className="button">Create poll</button>
          <button type="button" className="button secondary" onClick={() => setComposing(false)}>Cancel</button>
        </div>
      </form> : <button type="button" className="button secondary group-new-poll" onClick={() => setComposing(true)}>New poll</button>}
    </fieldset>}
  </section>;
}

// Listing threads only carry an id; look the title up so the picker and composer can name it.
function useListingTitle(id) {
  const [titles, setTitles] = useState({});
  useEffect(() => {
    if (!id || titles[id]) return;
    let active = true;
    getListing(id).then(listing => { if (active) setTitles(all => ({ ...all, [id]: comparisonTitle(listing) })); }).catch(() => {});
    return () => { active = false; };
  }, [id, titles]);
  return id ? titles[id] : undefined;
}

export default function GroupRoom({ path, listing, comparison, comparisons }) {
  const [thread, setThread] = useState(comparison ? "comparison_id:" + comparison : listing ? "listing_id:" + listing : "");
  const [kind, threadId] = thread.split(":");
  const listingTitle = useListingTitle(kind === "listing_id" ? threadId : listing);
  const options = new Map(comparisons.map(item => ["comparison_id:" + item.id, item.title || "Comparison by " + item.saved_by.name]));
  if (listing && !options.has("listing_id:" + listing)) options.set("listing_id:" + listing, "Listing");
  if (thread && !options.has(thread)) options.set(thread, kind === "listing_id" ? "Listing" : "Comparison");
  // Name listing threads after the listing once its title has loaded.
  if (kind === "listing_id" && listingTitle) options.set(thread, listingTitle);
  else if (listing && listingTitle) options.set("listing_id:" + listing, listingTitle);
  const choices = [...options];
  const about = thread ? options.get(thread) : "";
  return <section className="card group-discussion">
    <div className="group-section-head">
      <h2>Discussion</h2>
      <label className="group-thread-picker"><span className="muted">Thread</span>
        <select value={thread} onChange={event => setThread(event.target.value)}>
          <option value="">All messages</option>{choices.map(([key, label]) => <option value={key} key={key}>{label}</option>)}
        </select></label>
    </div>
    {kind === "listing_id" && <p className="group-thread-context">Thread about <strong>{listingTitle || "this listing"}</strong> · <Link href={"/listings/" + threadId}><a>View listing →</a></Link></p>}
    {kind === "comparison_id" && <SharedComparison key={"table:" + thread} id={threadId} />}
    <Discussion key={"feed:" + thread} path={path} thread={thread} about={about} selectThread={setThread} />
  </section>;
}
