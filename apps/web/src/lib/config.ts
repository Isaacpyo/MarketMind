/** Base URL of the FastAPI backend (no trailing slash). Baked in at build time. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

/** After this long without a response we assume the free-tier server is asleep. */
export const SLOW_REQUEST_MS = 2500;
/** A cold start on Render's free tier usually takes 30–60s; give up waiting after this. */
export const UNREACHABLE_AFTER_MS = 120_000;
/** Per-request timeout. Generous, because the first request is what wakes the server. */
export const REQUEST_TIMEOUT_MS = 90_000;
