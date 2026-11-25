import Link from "next/link";
import AccountWorkspace from "@/components/AccountWorkspace";
import { Feedback, shortDate, useGroupData } from "@/components/GroupWorkspace";

const load = request => request("/comparisons");
function Library() {
  const state = useGroupData(load);
  return <><Feedback state={state} />{state.data && (state.data.length ? <section className="card">
    <ul className="group-list">{state.data.map(item => <li key={item.id}>
      <Link href={"/comparisons/" + item.id}><a className="group-link">
        <span><strong>{item.title || "Untitled comparison"}</strong>
          <span className="muted">{item.listing_ids.length} listings · Saved {shortDate(item.saved_at)}</span></span>
        <span aria-hidden="true" className="group-link-arrow">→</span>
      </a></Link>
    </li>)}</ul>
    <p className="muted account-footnote">Comparisons you share with a group move to that group’s room.</p>
  </section> : <section className="card account-empty">
    <h2>No saved comparisons yet</h2>
    <p className="muted">Pick two to four listings, compare them, then save the table here to revisit later. You’ll see what changed since you saved it.</p>
    <Link href="/compare"><a className="button">Compare listings</a></Link>
  </section>)}</>;
}
export default function Comparisons() {
  return <AccountWorkspace title="My comparisons" back={{ href: "/compare", label: "Compare" }}>
    {user => <Library key={user.id} />}
  </AccountWorkspace>;
}
