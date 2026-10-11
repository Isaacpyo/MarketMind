import type { NextConfig } from "next";

// Netlify sets NETLIFY=true and CONTEXT=production for production deploys. Shipping a bundle
// that points at localhost would look like a broken site, so fail the build instead.
if (process.env.NETLIFY === "true" && process.env.CONTEXT === "production" && !process.env.NEXT_PUBLIC_API_URL) {
  throw new Error("NEXT_PUBLIC_API_URL must be set in Netlify's environment variables (the Render API URL).");
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const isProd = process.env.NODE_ENV === "production";

// The bearer token lives in localStorage, so a strict-ish CSP is our main XSS backstop.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiUrl}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  // Docker builds a self-contained server; Netlify uses its own Next.js runtime.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    const securityHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ];
    if (isProd) securityHeaders.push({ key: "Content-Security-Policy", value: csp });
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
