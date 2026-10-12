"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { makeQueryClient } from "@/lib/query-client";
import { ServerStatusProvider } from "@/lib/server-status-context";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <ServerStatusProvider>
        <AuthProvider>{children}</AuthProvider>
      </ServerStatusProvider>
    </QueryClientProvider>
  );
}
