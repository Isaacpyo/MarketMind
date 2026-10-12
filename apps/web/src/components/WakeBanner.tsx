"use client";

import { Coffee, LoaderCircle, RefreshCw, Server } from "lucide-react";
import { useEffect, useState } from "react";
import { formatDuration } from "@/lib/format";
import { isWaiting } from "@/lib/server-status";
import { useServerStatus } from "@/lib/server-status-context";

/** Explains the free-tier cold start instead of leaving the page looking broken. */
export function WakeBanner() {
  const { state, retry } = useServerStatus();
  const waiting = isWaiting(state);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [waiting]);

  const elapsed = state.waitingSince ? Math.max(0, (now - state.waitingSince) / 1000) : 0;

  return (
    <div aria-live="polite" role="status">
      {waiting ? (
        <div className="border-b border-amber-200 bg-amber-50">
          <div className="container-page flex flex-col gap-2 py-3 text-sm text-amber-950 sm:flex-row sm:items-center sm:justify-between">
            {state.phase === "unreachable" ? (
              <>
                <p className="flex items-start gap-2">
                  <Server className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <span>
                    <strong>We can&apos;t reach the server right now.</strong> It may be restarting. Please try again
                    in a minute.
                  </span>
                </p>
                <button type="button" onClick={retry} className="btn-secondary self-start py-1.5 sm:self-auto">
                  <RefreshCw className="size-4" aria-hidden="true" /> Retry
                </button>
              </>
            ) : (
              <>
                <p className="flex items-start gap-2">
                  {state.phase === "waking" ? (
                    <Coffee className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  ) : (
                    <LoaderCircle className="mt-0.5 size-4 shrink-0 animate-spin" aria-hidden="true" />
                  )}
                  <span>
                    {state.phase === "waking" ? (
                      <>
                        <strong>Waking the server…</strong> This demo runs on a free tier that sleeps when idle.
                        The first request takes about 30–60 seconds.
                      </>
                    ) : (
                      <>
                        <strong>Server is awake</strong> and is loading the catalogue and recommendation model…
                      </>
                    )}
                  </span>
                </p>
                <span className="shrink-0 tabular-nums text-amber-800" aria-hidden="true">
                  {formatDuration(elapsed)}
                </span>
              </>
            )}
          </div>
          <div className="h-0.5 overflow-hidden bg-amber-100" aria-hidden="true">
            <div className="h-full w-1/3 animate-[wake_1.6s_ease-in-out_infinite] bg-amber-400" />
          </div>
        </div>
      ) : null}
    </div>
  );
}
