import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback } from "react";
import AccountWorkspace from "@/components/AccountWorkspace";
import GroupPicker from "@/components/GroupPicker";
import { Feedback, shortDate, useGroupData } from "@/components/GroupWorkspace";
import SavedComparisonTable from "@/components/SavedComparisonTable";
import { comparisonTitle, useComparison } from "@/lib/comparison";

function Detail({ id, user }) {
  const path = "/comparisons/" + encodeURIComponent(id);
  const load = useCallback(request => request(path), [path]);
  const state = useGroupData(load);
  const saved = state.data;
  const router = useRouter();
  const { replace } = useComparison();
  const room = groupId => ({ pathname: "/groups/[id]", query: { id: groupId, comparison: id } });
  // Removed listings can't be previewed again, so only the live ones go back into the selection.
  const removed = new Set((saved?.changes || []).filter(change => change.state === "removed").map(change => change.listing_id));
  const live = saved ? saved.table.listings.filter(listing => !removed.has(listing.id)) : [];
  function compareAgain() {
    replace(live.map(listing => ({ id: listing.id, title: comparisonTitle(listing) })));
    router.push("/compare");
  }
  if (!saved) return <><h1>Saved comparison</h1><Feedback state={state} /></>;
  return <>
    <div className="account-title">
      <div>
        <h1>{saved.title || "Untitled comparison"}</h1>
        <p className="muted account-subtitle">{saved.table.listings.length} listings · saved by {saved.saved_by.id === user.id ? "you" : saved.saved_by.name} on {shortDate(saved.saved_at)}</p>
      </div>
      <div className="group-row-actions">
        {live.length >= 2 && <button type="button" className="button secondary" onClick={compareAgain}>Compare with current data</button>}
        {saved.group_id ? <Link href={room(saved.group_id)}><a className="button">Open group discussion</a></Link> :
          saved.saved_by.id === user.id && <GroupPicker label="Share to group" confirmLabel="Share and discuss"
            onConfirm={async (request, groupId) => {
              const shared = await request(path + "/share", { method: "POST", body: { group_id: groupId } });
              state.update(shared);
              return room(groupId);
            }} />}
      </div>
    </div>
    <Feedback state={state} />
    <SavedComparisonTable comparison={saved} standalone />
  </>;
}
export default function Comparison() {
  const { query } = useRouter();
  return <AccountWorkspace title="Saved comparison" heading={false} wide back={{ href: "/comparisons", label: "My comparisons" }}>
    {user => <Detail key={user.id + query.id} id={query.id} user={user} />}
  </AccountWorkspace>;
}
