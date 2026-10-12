import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, buildUrl, errorMessage, onSlowRequest, onUnauthorized, setAuthToken } from "@/lib/api/client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("errorMessage", () => {
  it("uses FastAPI's string detail", () => {
    expect(errorMessage(409, { detail: "An account with this email already exists" })).toBe(
      "An account with this email already exists",
    );
  });

  it("flattens 422 validation issues into one sentence", () => {
    const body = {
      detail: [
        { loc: ["body", "email"], msg: "value is not a valid email address" },
        { loc: ["body", "password"], msg: "String should have at least 8 characters" },
      ],
    };
    expect(errorMessage(422, body)).toBe(
      "email: value is not a valid email address; password: String should have at least 8 characters",
    );
  });

  it("falls back to friendly generic messages", () => {
    expect(errorMessage(0, null)).toMatch(/Can't reach the server/);
    expect(errorMessage(500, null)).toMatch(/server had a problem/);
    expect(errorMessage(418, null)).toBe("Request failed (418)");
  });
});

describe("buildUrl", () => {
  it("prefixes /api and drops empty query values", () => {
    expect(buildUrl("/products", { q: "red mug", category: "", page: 2, sort: undefined })).toBe(
      "http://localhost:8000/api/products?q=red+mug&page=2",
    );
  });
});

describe("api", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    setAuthToken(null);
    onUnauthorized(null);
  });

  it("sends JSON with the bearer token and parses the response", async () => {
    setAuthToken("tok");
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true }));
    await expect(api("/cart/items", { method: "POST", body: { product_id: "10001" } })).resolves.toEqual({ ok: true });
    const [, init] = fetchMock.mock.calls[0]!;
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe('{"product_id":"10001"}');
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("raises ApiError and signs the shopper out on 401", async () => {
    const handler = vi.fn();
    setAuthToken("expired");
    onUnauthorized(handler);
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: "Your session has expired" }));
    const error = await api("/cart").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
    expect((error as ApiError).isTransient).toBe(false);
    expect(handler).toHaveBeenCalledOnce();
  });

  it("marks network failures and 503s as transient", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const network = (await api("/health").catch((e: unknown) => e)) as ApiError;
    expect(network.status).toBe(0);
    expect(network.isTransient).toBe(true);

    fetchMock.mockResolvedValueOnce(jsonResponse(503, { detail: "Catalogue is still loading" }));
    const loading = (await api("/products").catch((e: unknown) => e)) as ApiError;
    expect(loading.isTransient).toBe(true);
    expect(loading.message).toBe("Catalogue is still loading");
  });

  it("notifies listeners when a request is slow (server waking up)", async () => {
    vi.useFakeTimers();
    const slow = vi.fn();
    const off = onSlowRequest(slow);
    let resolve!: (r: Response) => void;
    fetchMock.mockReturnValue(new Promise<Response>((r) => (resolve = r)));
    const pending = api("/health");
    await vi.advanceTimersByTimeAsync(2_000);
    expect(slow).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(600);
    expect(slow).toHaveBeenCalledOnce();
    resolve(jsonResponse(200, { status: "ok" }));
    await expect(pending).resolves.toEqual({ status: "ok" });
    off();
  });
});
