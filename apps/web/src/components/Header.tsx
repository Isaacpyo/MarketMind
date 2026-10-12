"use client";

import clsx from "clsx";
import { Brain, LogOut, Menu, Search, ShoppingCart, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import { useAuth } from "@/lib/auth";
import { useCart } from "@/lib/hooks";

function SearchForm({ className }: { className?: string }) {
  const router = useRouter();
  const id = useId();
  const [q, setQ] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    router.push(q.trim() ? `/products?q=${encodeURIComponent(q.trim())}` : "/products");
  }

  return (
    <form role="search" onSubmit={onSubmit} className={clsx("relative", className)}>
      <label htmlFor={id} className="sr-only">
        Search products
      </label>
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
      <input
        id={id}
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search mugs, bunting, lanterns…"
        maxLength={80}
        className="input pl-9"
      />
    </form>
  );
}

export function Header() {
  const { user, status, signOut } = useAuth();
  const cart = useCart();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const count = cart.data?.item_count ?? 0;

  const links = [
    { href: "/products", label: "Shop" },
    ...(user ? [{ href: "/orders", label: "Orders" }] : []),
    ...(user?.role === "admin" ? [{ href: "/admin", label: "Model admin" }] : []),
  ];

  const navLink = (href: string, label: string, mobile = false) => (
    <Link
      key={href}
      href={href}
      onClick={() => setMenuOpen(false)}
      aria-current={pathname.startsWith(href) ? "page" : undefined}
      className={clsx(
        "rounded-md font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 aria-[current=page]:text-brand-800",
        mobile ? "block px-3 py-2.5 text-base" : "px-3 py-2 text-sm",
      )}
    >
      {label}
    </Link>
  );

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="container-page flex h-16 items-center gap-3">
        <Link href="/" className="flex shrink-0 items-center gap-2 rounded-md font-semibold text-slate-900">
          <span className="flex size-8 items-center justify-center rounded-lg bg-brand-700 text-white">
            <Brain className="size-5" aria-hidden="true" />
          </span>
          <span className="text-lg tracking-tight">MarketMind</span>
        </Link>

        <SearchForm className="mx-4 hidden max-w-md flex-1 md:block" />

        <nav aria-label="Main" className="ml-auto hidden items-center gap-1 md:flex">
          {links.map((l) => navLink(l.href, l.label))}
        </nav>

        <div className="ml-auto flex items-center gap-1 md:ml-2">
          <Link
            href="/cart"
            className="relative rounded-lg p-2 text-slate-700 hover:bg-slate-100"
            aria-label={count > 0 ? `Cart, ${count} items` : "Cart"}
          >
            <ShoppingCart className="size-5" aria-hidden="true" />
            {count > 0 ? (
              <span className="absolute -right-0.5 -top-0.5 flex min-w-5 items-center justify-center rounded-full bg-brand-700 px-1 text-[11px] font-bold text-white">
                {count > 99 ? "99+" : count}
              </span>
            ) : null}
          </Link>

          <div className="hidden md:flex md:items-center md:gap-1">
            {status === "authenticated" && user ? (
              <>
                <span className="max-w-40 truncate px-2 text-sm text-slate-600" title={user.email}>
                  Hi, {user.name.split(" ")[0]}
                </span>
                <button type="button" onClick={signOut} className="btn-ghost px-3 py-2">
                  <LogOut className="size-4" aria-hidden="true" /> Sign out
                </button>
              </>
            ) : status === "anonymous" ? (
              <Link href="/login" className="btn-primary py-2">
                Sign in
              </Link>
            ) : null}
          </div>

          <button
            type="button"
            className="rounded-lg p-2 text-slate-700 hover:bg-slate-100 md:hidden"
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X className="size-5" aria-hidden="true" /> : <Menu className="size-5" aria-hidden="true" />}
          </button>
        </div>
      </div>

      <div className="container-page pb-3 md:hidden">
        <SearchForm />
      </div>

      {menuOpen ? (
        <div id="mobile-menu" className="border-t border-slate-200 bg-white md:hidden">
          <nav aria-label="Mobile" className="container-page space-y-1 py-3">
            {links.map((l) => navLink(l.href, l.label, true))}
            {user ? (
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  signOut();
                }}
                className="block w-full rounded-md px-3 py-2.5 text-left text-base font-medium text-slate-700 hover:bg-slate-100"
              >
                Sign out ({user.name})
              </button>
            ) : (
              navLink("/login", "Sign in", true)
            )}
          </nav>
        </div>
      ) : null}
    </header>
  );
}
