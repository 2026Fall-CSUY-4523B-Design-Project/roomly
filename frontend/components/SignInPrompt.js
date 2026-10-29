import Link from "next/link";
import { useRouter } from "next/router";

// Shown in place of a page that needs an account (guests may search and compare, R-1).
export default function SignInPrompt({ what }) {
  const router = useRouter();
  const next = encodeURIComponent(router.asPath);
  return (
    <div className="empty">
      <h3>Sign in to {what}</h3>
      <p>Guests can search and compare listings. Groups, saved searches and notifications need an account.</p>
      <div className="row" style={{ justifyContent: "center" }}>
        <Link href={`/sign-in?next=${next}`}>
          <a className="btn btn-primary">Sign in</a>
        </Link>
        <Link href={`/sign-up?next=${next}`}>
          <a className="btn btn-ghost">Create account</a>
        </Link>
      </div>
    </div>
  );
}
