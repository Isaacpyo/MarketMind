import { setAuthToken } from "@/lib/api/client";

/**
 * The session token, kept in localStorage and exposed as an external store so React reads
 * it with useSyncExternalStore (no setState-in-effect, and tabs stay in sync).
 */
const TOKEN_KEY = "marketmind.token";
const listeners = new Set<() => void>();
let cached: string | null | undefined;

function read(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // storage blocked (private mode, sandboxed iframe)
  }
}

function write(token: string | null): void {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* the session simply won't survive a reload */
  }
}

export const tokenStore = {
  get(): string | null {
    if (cached === undefined) {
      cached = read();
      setAuthToken(cached);
    }
    return cached;
  },
  /** Before hydration we don't know yet whether the visitor is signed in. */
  getServer(): undefined {
    return undefined;
  },
  set(token: string | null): void {
    cached = token;
    setAuthToken(token);
    write(token);
    listeners.forEach((listener) => listener());
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    const onStorage = (event: StorageEvent) => {
      if (event.key !== TOKEN_KEY) return;
      cached = event.newValue;
      setAuthToken(cached);
      listener();
    };
    window.addEventListener("storage", onStorage);
    return () => {
      listeners.delete(listener);
      window.removeEventListener("storage", onStorage);
    };
  },
  /** Test helper. */
  reset(): void {
    cached = undefined;
  },
};
