import Head from "next/head";

import SprintNotice from "@/components/SprintNotice";

// Comparison (§8.1.2.6, R-4). The API is complete; the side-by-side table lands with Sprint 4.
export default function ComparePage() {
  return (
    <div className="container page">
      <Head>
        <title>Compare · Roomly</title>
      </Head>
      <p className="eyebrow">Comparison</p>
      <h1>Line them up, side by side.</h1>
      <p className="lede">
        Pick two to four listings and see every value aligned. The best value is highlighted only when at least
        two listings have a known value that isn&rsquo;t tied; Unknown is never &ldquo;best&rdquo;.
      </p>
      <div style={{ marginTop: 28 }}>
        <SprintNotice
          sprint={4}
          title="The comparison table"
          items={[
            "Add listings from search results or a listing card",
            "Aligned rows for rent, fees, size, price per sq ft (with its formula) and commute",
            "Save a comparison, share it with your group, and see which values changed since you saved it",
          ]}
          endpoints={[
            "POST /comparisons/preview",
            "POST /comparisons",
            "GET /comparisons/{id}",
            "POST /comparisons/{id}/share",
          ]}
        >
          Guests can compare; saving and sharing need an account.
        </SprintNotice>
      </div>
    </div>
  );
}
