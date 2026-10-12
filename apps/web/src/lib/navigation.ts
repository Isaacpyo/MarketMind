/** Only allow same-site relative redirects, so `?next=` can't become an open redirect. */
export function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.startsWith("/\\") ? value : "/";
}
