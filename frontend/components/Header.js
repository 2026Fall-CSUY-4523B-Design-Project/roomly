import Link from "next/link";

// Top navigation. Routes other than / are planned (SSDS §16.6.1 WebClient) and not built yet.
export default function Header() {
  return (
    <header className="header">
      <Link href="/">
        <a className="brand">Roomly</a>
      </Link>
      <nav className="nav" aria-label="Main">
        <Link href="/">
          <a>Search</a>
        </Link>
        <Link href="/compare">
          <a>Compare</a>
        </Link>
        <Link href="/groups">
          <a>Groups</a>
        </Link>
        <Link href="/notifications">
          <a>Notifications</a>
        </Link>
        <Link href="/sign-in">
          <a className="button">Sign in</a>
        </Link>
      </nav>
    </header>
  );
}
