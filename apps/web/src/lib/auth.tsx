"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";
import { api, onUnauthorized } from "@/lib/api/client";
import type { AuthOut, User } from "@/lib/api/types";
import { tokenStore } from "@/lib/token-store";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  signIn: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string) => Promise<User>;
  startDemo: () => Promise<User>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const token = useSyncExternalStore(tokenStore.subscribe, tokenStore.get, tokenStore.getServer);

  const applyToken = useCallback(
    (next: string | null) => {
      tokenStore.set(next);
      // Anything cached for the previous shopper is now wrong.
      queryClient.removeQueries({ queryKey: ["user"] });
    },
    [queryClient],
  );

  useEffect(() => {
    onUnauthorized(() => applyToken(null));
    return () => onUnauthorized(null);
  }, [applyToken]);

  const me = useQuery({
    queryKey: ["user", "me", token],
    queryFn: ({ signal }) => api<User>("/auth/me", { signal }),
    enabled: Boolean(token),
    staleTime: 5 * 60_000,
  });

  const finish = useCallback(
    (result: AuthOut) => {
      applyToken(result.access_token);
      queryClient.setQueryData(["user", "me", result.access_token], result.user);
      return result.user;
    },
    [applyToken, queryClient],
  );

  const value = useMemo<AuthContextValue>(() => {
    let status: AuthStatus = "anonymous";
    if (token === undefined || (token && me.isPending)) status = "loading";
    else if (token && me.data) status = "authenticated";
    return {
      user: token ? (me.data ?? null) : null,
      status,
      signIn: async (email, password) =>
        finish(await api<AuthOut>("/auth/login", { method: "POST", body: { email, password } })),
      register: async (name, email, password) =>
        finish(await api<AuthOut>("/auth/register", { method: "POST", body: { name, email, password } })),
      startDemo: async () => finish(await api<AuthOut>("/auth/demo", { method: "POST" })),
      signOut: () => applyToken(null),
    };
  }, [applyToken, finish, me.data, me.isPending, token]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
