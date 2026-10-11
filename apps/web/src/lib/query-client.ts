import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";

export const MAX_TRANSIENT_RETRIES = 8;

/** Retry while the server is waking (network errors, 502–504); never on 4xx. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  return error instanceof ApiError && error.isTransient && failureCount < MAX_TRANSIENT_RETRIES;
}

export function retryDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, 8000);
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: shouldRetry, retryDelay, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}
