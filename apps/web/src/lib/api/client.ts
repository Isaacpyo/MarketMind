import { API_URL, REQUEST_TIMEOUT_MS, SLOW_REQUEST_MS } from "@/lib/config";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True for errors worth retrying: the server is down, waking up or still loading. */
  get isTransient(): boolean {
    return this.status === 0 || this.status === 502 || this.status === 503 || this.status === 504;
  }
}

type ValidationIssue = { loc?: (string | number)[]; msg?: string };

/** Turn FastAPI's error payloads (string or 422 issue list) into one readable sentence. */
export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return (detail as ValidationIssue[])
      .map((issue) => {
        const field = issue.loc?.filter((part) => part !== "body").join(".");
        return field ? `${field}: ${issue.msg ?? "invalid"}` : (issue.msg ?? "invalid input");
      })
      .join("; ");
  }
  if (status === 0) return "Can't reach the server. Check your connection and try again.";
  if (status >= 500) return "The server had a problem. Please try again in a moment.";
  return `Request failed (${status})`;
}

type Listener = () => void;
const slowListeners = new Set<Listener>();
const transientListeners = new Set<Listener>();

/** Notified when any request is slow (server probably asleep) or fails transiently. */
export function onSlowRequest(listener: Listener): () => void {
  slowListeners.add(listener);
  return () => slowListeners.delete(listener);
}

export function onTransientFailure(listener: Listener): () => void {
  transientListeners.add(listener);
  return () => transientListeners.delete(listener);
}

let authToken: string | null = null;
let unauthorizedHandler: Listener | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function onUnauthorized(handler: Listener | null): void {
  unauthorizedHandler = handler;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
  signal?: AbortSignal;
  timeoutMs?: number;
  keepalive?: boolean;
}

export function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_URL}/api${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  return url.toString();
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal, timeoutMs = REQUEST_TIMEOUT_MS, keepalive } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const timeout = AbortSignal.timeout(timeoutMs);
  const slowTimer = setTimeout(() => slowListeners.forEach((fn) => fn()), SLOW_REQUEST_MS);
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      keepalive,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    transientListeners.forEach((fn) => fn());
    throw new ApiError(0, errorMessage(0, null));
  } finally {
    clearTimeout(slowTimer);
  }

  const payload: unknown = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const error = new ApiError(response.status, errorMessage(response.status, payload));
    if (error.isTransient) transientListeners.forEach((fn) => fn());
    if (response.status === 401 && authToken) unauthorizedHandler?.();
    throw error;
  }
  return payload as T;
}
