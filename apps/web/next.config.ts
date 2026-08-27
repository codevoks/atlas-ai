import type { NextConfig } from "next";
import path from "node:path";

const isDevelopment = process.env.NODE_ENV !== "production";
const workspaceRoot = path.resolve(import.meta.dirname, "../..");
const scriptSources = [
  "'self'",
  "'unsafe-inline'",
  ...(isDevelopment ? ["'unsafe-eval'"] : []),
  "https://*.clerk.accounts.dev",
];

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src ${scriptSources.join(" ")}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https://img.clerk.com",
  "font-src 'self'",
  "connect-src 'self' http://localhost:8000 https://*.clerk.accounts.dev",
  "frame-src 'self' https://*.clerk.accounts.dev",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self' https://*.clerk.accounts.dev",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  turbopack: {
    root: workspaceRoot,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
