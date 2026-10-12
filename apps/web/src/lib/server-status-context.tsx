"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useReducer, useRef, type ReactNode } from "react";
import { api, onSlowRequest, onTransientFailure } from "@/lib/api/client";
import type { Health } from "@/lib/api/types";
import { initialServerState, reduceServerState, type ServerState } from "@/lib/server-status";

const POLL_MS = 3000;

interface ServerStatusValue {
  state: ServerState;
  retry: () => void;
}

const ServerStatusContext = createContext<ServerStatusValue | null>(null);

export function ServerStatusProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, dispatch] = useReducer(reduceServerState, initialServerState);
  const polling = useRef(false);
  const phase = useRef(state.phase);
  useEffect(() => {
    phase.current = state.phase;
  }, [state.phase]);

  const poll = useCallback(async () => {
    if (polling.current) return;
    polling.current = true;
    try {
      while (phase.current !== "unreachable") {
        try {
          const health = await api<Health>("/health", { timeoutMs: 20_000 });
          dispatch({ type: "healthy", ready: health.ready, at: Date.now() });
          if (health.ready) break;
        } catch {
          dispatch({ type: "failed", at: Date.now() });
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
      }
    } finally {
      polling.current = false;
    }
  }, []);

  useEffect(() => {
    void poll();
    const wake = () => {
      dispatch({ type: "slow", at: Date.now() });
      void poll();
    };
    const offSlow = onSlowRequest(wake);
    const offFail = onTransientFailure(wake);
    return () => {
      offSlow();
      offFail();
    };
  }, [poll]);

  // Once the server is back, re-run anything that failed while it slept.
  const previous = useRef(state.phase);
  useEffect(() => {
    if (state.phase === "ready" && previous.current !== "ready" && previous.current !== "checking") {
      void queryClient.refetchQueries({ type: "active", predicate: (q) => q.state.status === "error" });
    }
    previous.current = state.phase;
  }, [queryClient, state.phase]);

  const retry = useCallback(() => {
    dispatch({ type: "retry", at: Date.now() });
    phase.current = "waking";
    void poll();
  }, [poll]);

  return <ServerStatusContext.Provider value={{ state, retry }}>{children}</ServerStatusContext.Provider>;
}

export function useServerStatus(): ServerStatusValue {
  const ctx = useContext(ServerStatusContext);
  if (!ctx) throw new Error("useServerStatus must be used inside <ServerStatusProvider>");
  return ctx;
}
