import Head from "next/head";

import Header from "@/components/Header";

// Shell shared by the account pages: title, header and the centred card.
export default function AuthPage({ title, noReferrer = false, children }) {
  return <>
    <Head>
      <title>{title} · Roomly</title>
      {noReferrer && <meta name="referrer" content="no-referrer" />}
    </Head>
    <Header />
    <main className="auth-panel card">
      <h1>{title}</h1>
      {children}
    </main>
  </>;
}
