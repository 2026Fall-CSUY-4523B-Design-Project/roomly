import { ComparisonProvider } from "@/lib/comparison";

import { AuthProvider } from "@/lib/auth";

import "@/styles/globals.css";

export default function App({ Component, pageProps }) {
  return <AuthProvider><ComparisonProvider><Component {...pageProps} /></ComparisonProvider></AuthProvider>;
}
