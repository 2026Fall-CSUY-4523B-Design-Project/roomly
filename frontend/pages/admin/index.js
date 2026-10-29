import Head from "next/head";

import SignInPrompt from "@/components/SignInPrompt";
import SprintNotice from "@/components/SprintNotice";
import { useSession } from "@/lib/useSession";

// Data administration (§8.1.2.4, R-5). Admin accounts are granted with `script/backend.sh admin <email>`.
export default function AdminPage() {
  const { session, ready } = useSession();
  if (!ready) return <div className="container page" />;
  if (!session) {
    return (
      <div className="container page">
        <SignInPrompt what="open data administration" />
      </div>
    );
  }
  if (session.user.role !== "admin") {
    return (
      <div className="container page">
        <div className="empty">
          <h3>Administrators only</h3>
          <p>This area reviews listing sources, duplicates and data reports.</p>
        </div>
      </div>
    );
  }
  return (
    <div className="container page">
      <Head>
        <title>Admin · Roomly</title>
      </Head>
      <p className="eyebrow">Data administration</p>
      <h1>Keep the listings honest.</h1>
      <p className="lede">
        Every merge, split and source change is logged with who made it and why.
      </p>
      <div className="split" style={{ marginTop: 28 }}>
        <SprintNotice
          sprint={4}
          title="Duplicate review queue"
          items={[
            "Side-by-side candidates with the evidence that flagged them",
            "Merge, keep separate, or split an earlier merge",
            "Resolve user reports of wrong values or wrong merges",
          ]}
          endpoints={[
            "GET /admin/duplicates",
            "POST /admin/duplicates/{id}/merge",
            "POST /admin/duplicates/{id}/split",
            "GET /admin/reports",
          ]}
        />
        <SprintNotice
          sprint={3}
          compact
          title="Sources"
          items={["Enable or pause a source", "SampleFeed ingestion and normalization"]}
          endpoints={["GET /admin/sources", "POST /admin/sources", "PATCH /admin/sources/{id}"]}
        />
      </div>
    </div>
  );
}
