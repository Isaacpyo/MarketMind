import { describe, expect, it } from "vitest";
import { UNREACHABLE_AFTER_MS } from "@/lib/config";
import { initialServerState, isWaiting, reduceServerState, type ServerState } from "@/lib/server-status";

describe("reduceServerState", () => {
  it("goes straight to ready when the first health check is fast", () => {
    const next = reduceServerState(initialServerState, { type: "healthy", ready: true, at: 100 });
    expect(next.phase).toBe("ready");
    expect(isWaiting(next)).toBe(false);
  });

  it("shows the waking state when a request is slow, and remembers when waiting began", () => {
    const waking = reduceServerState(initialServerState, { type: "slow", at: 1_000 });
    expect(waking).toEqual({ phase: "waking", waitingSince: 1_000, failures: 0 });
    expect(isWaiting(waking)).toBe(true);
    // Further slow signals don't reset the clock.
    expect(reduceServerState(waking, { type: "slow", at: 5_000 }).waitingSince).toBe(1_000);
  });

  it("moves to preparing while the catalogue loads, then ready", () => {
    const waking: ServerState = { phase: "waking", waitingSince: 0, failures: 2 };
    const preparing = reduceServerState(waking, { type: "healthy", ready: false, at: 30_000 });
    expect(preparing).toEqual({ phase: "preparing", waitingSince: 0, failures: 0 });
    expect(reduceServerState(preparing, { type: "healthy", ready: true, at: 35_000 }).phase).toBe("ready");
  });

  it("gives up after the unreachable timeout and can be retried", () => {
    let state = reduceServerState(initialServerState, { type: "failed", at: 0 });
    expect(state.phase).toBe("waking");
    state = reduceServerState(state, { type: "failed", at: UNREACHABLE_AFTER_MS - 1 });
    expect(state.phase).toBe("waking");
    state = reduceServerState(state, { type: "failed", at: UNREACHABLE_AFTER_MS });
    expect(state).toMatchObject({ phase: "unreachable", failures: 3 });
    expect(reduceServerState(state, { type: "retry", at: 999_999 })).toEqual({
      phase: "waking",
      waitingSince: 999_999,
      failures: 0,
    });
  });

  it("re-enters waking if a ready server goes back to sleep", () => {
    const ready: ServerState = { phase: "ready", waitingSince: null, failures: 0 };
    expect(reduceServerState(ready, { type: "slow", at: 42 }).phase).toBe("waking");
  });
});
