import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container page">
      <p className="eyebrow">404</p>
      <h1>This place isn&rsquo;t on the market.</h1>
      <p className="lede">The page you asked for doesn&rsquo;t exist, or the link is out of date.</p>
      <Link href="/">
        <a className="btn btn-primary">Back to search</a>
      </Link>
    </div>
  );
}
