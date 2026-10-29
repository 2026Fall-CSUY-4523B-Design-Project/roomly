import Head from "next/head";

import SignInPrompt from "@/components/SignInPrompt";
import SprintNotice from "@/components/SprintNotice";
import { useSession } from "@/lib/useSession";

// Notifications (§8.1.2.8, R-6). Stored and served today; the inbox and settings land in Sprint 5.
export default function NotificationsPage() {
  const { session, ready } = useSession();
  return (
    <div className="container page">
      <Head>
        <title>Notifications · Roomly</title>
      </Head>
      <p className="eyebrow">Notifications</p>
      <h1>What changed while you were away.</h1>
      <p className="lede">
        New messages and polls in your groups, and price or availability changes on listings you saved, each
        delivered once.
      </p>
      <div className="stack" style={{ marginTop: 28 }}>
        {ready && !session ? <SignInPrompt what="see your notifications" /> : null}
        <SprintNotice
          sprint={5}
          title="Inbox and delivery settings"
          items={[
            "An inbox with unread counts, mark one or all as read",
            "Choose which kinds you get, email on or off, a daily digest, and quiet hours",
            "Email delivery and the digest worker",
          ]}
          endpoints={["GET /notifications", "POST /notifications/read-all", "PUT /me/notification-settings"]}
        />
      </div>
    </div>
  );
}
