/**
 * Tracks whether the API is awake. Render's free tier sleeps after ~15 idle minutes and
 * takes 30–60s to wake, so the UI explains the delay instead of looking broken.
 */
import { UNREACHABLE_AFTER_MS } from "@/lib/config";

export type ServerPhase = "checking" | "waking" | "preparing" | "ready" | "unreachable";

export interface ServerState {
  phase: ServerPhase;
  /** When the current wait (waking/preparing) started, for the elapsed-time display. */
  waitingSince: number | null;
  failures: number;
}

export type ServerEvent =
  | { type: "slow"; at: number }
  | { type: "healthy"; ready: boolean; at: number }
  | { type: "failed"; at: number }
  | { type: "retry"; at: number };

export const initialServerState: ServerState = { phase: "checking", waitingSince: null, failures: 0 };

export function reduceServerState(state: ServerState, event: ServerEvent): ServerState {
  switch (event.type) {
    case "slow":
      if (state.phase === "checking" || state.phase === "ready") {
        return { phase: "waking", waitingSince: event.at, failures: 0 };
      }
      return state;
    case "healthy":
      if (event.ready) return { phase: "ready", waitingSince: null, failures: 0 };
      return {
        phase: "preparing",
        waitingSince: state.waitingSince ?? event.at,
        failures: 0,
      };
    case "failed": {
      const waitingSince = state.waitingSince ?? event.at;
      const failures = state.failures + 1;
      const phase = event.at - waitingSince >= UNREACHABLE_AFTER_MS ? "unreachable" : "waking";
      return { phase, waitingSince, failures };
    }
    case "retry":
      return { phase: "waking", waitingSince: event.at, failures: 0 };
  }
}

/** Whether the UI should show the wake-up banner. */
export function isWaiting(state: ServerState): boolean {
  return state.phase === "waking" || state.phase === "preparing" || state.phase === "unreachable";
}
