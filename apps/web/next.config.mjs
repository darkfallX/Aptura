import { fileURLToPath } from "node:url";
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.APTURA_NEXT_DIST_DIR || ".next",
  outputFileTracingRoot: fileURLToPath(new URL("./", import.meta.url)),
  async rewrites() {
    // Accept "https://host", "https://host/" or "https://host/api" alike.
    const apiBase = (process.env.APTURA_BACKEND_URL || "http://127.0.0.1:8000")
      .trim()
      .replace(/\/+$/, "")
      .replace(/\/api$/, "");
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
