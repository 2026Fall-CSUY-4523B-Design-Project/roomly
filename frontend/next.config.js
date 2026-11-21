/** @type {import('next').NextConfig} */
const backend = process.env.ROOMLY_API_URL || "http://127.0.0.1:8000";

module.exports = {
  reactStrictMode: true,
  // Same-origin /api/* in dev and prod; the browser never talks to the backend directly.
  // Emailed links carry a single-use token; keep it out of Referer headers sent from these pages.
  async headers() {
    const noReferrer = [{ key: "Referrer-Policy", value: "no-referrer" }];
    return [
      { source: "/verify-email", headers: noReferrer },
      { source: "/reset-password", headers: noReferrer },
    ];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
};
