import Head from "next/head";

import Layout from "@/components/Layout";

import "@/styles/globals.css";

export default function RoomlyApp({ Component, pageProps }) {
  return (
    <>
      <Head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Roomly</title>
      </Head>
      <Layout>
        <Component {...pageProps} />
      </Layout>
    </>
  );
}
