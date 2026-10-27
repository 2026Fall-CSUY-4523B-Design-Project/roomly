/** @type {import('next').NextConfig} */
const backend = process.env.ROOMLY_API_URL || "http://127.0.0.1:8000";

module.exports = {
  reactStrictMode: true,
  // Same-origin /api/* in dev and prod; the browser never talks to the backend directly.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
};
