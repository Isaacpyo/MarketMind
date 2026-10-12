"use client";

import { ShoppingBag, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProductArt } from "@/components/ProductArt";
import { RequireAuth } from "@/components/RequireAuth";
import { EmptyState, ErrorState, Spinner } from "@/components/States";
import { ApiError } from "@/lib/api/client";
import type { CartLine } from "@/lib/api/types";
import { formatPrice, pluralize } from "@/lib/format";
import { useCart, usePlaceOrder, useRemoveFromCart, useSetQuantity } from "@/lib/hooks";

const QUANTITIES = Array.from({ length: 20 }, (_, i) => i + 1);

function Line({ line }: { line: CartLine }) {
  const setQuantity = useSetQuantity();
  const remove = useRemoveFromCart();
  const busy = setQuantity.isPending || remove.isPending;
  const p = line.product;
  return (
    <li className="flex gap-3 py-4 sm:gap-4" aria-busy={busy}>
      <Link href={`/products/${p.id}`} className="shrink-0" tabIndex={-1} aria-hidden="true">
        <ProductArt productId={p.id} category={p.category} size="sm" className="size-20 rounded-lg sm:size-24" />
      </Link>
      <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <Link href={`/products/${p.id}`} className="line-clamp-2 font-medium text-slate-900 hover:text-brand-800">
            {p.title}
          </Link>
          <p className="text-sm text-slate-600">{formatPrice(p.price)} each</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="sr-only" htmlFor={`qty-${p.id}`}>
            Quantity for {p.title}
          </label>
          <select
            id={`qty-${p.id}`}
            className="input w-20 py-2"
            value={line.quantity}
            disabled={busy}
            onChange={(e) => setQuantity.mutate({ productId: p.id, quantity: Number(e.target.value) })}
          >
            {QUANTITIES.map((q) => (
              <option key={q} value={q}>
                {q}
              </option>
            ))}
          </select>
          <p className="w-20 text-right font-semibold tabular-nums">{formatPrice(line.line_total)}</p>
          <button
            type="button"
            className="rounded-lg p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50"
            onClick={() => remove.mutate(p.id)}
            disabled={busy}
            aria-label={`Remove ${p.title} from cart`}
          >
            <Trash2 className="size-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </li>
  );
}

function CartContents() {
  const cart = useCart();
  const placeOrder = usePlaceOrder();
  const router = useRouter();

  if (cart.isPending) {
    return (
      <div className="py-16 text-center">
        <Spinner label="Loading your cart" />
      </div>
    );
  }
  if (cart.error) {
    return <ErrorState message={cart.error instanceof ApiError ? cart.error.message : "Couldn't load your cart."} onRetry={() => void cart.refetch()} />;
  }
  if (cart.data.items.length === 0) {
    return (
      <EmptyState
        title="Your cart is empty"
        icon={<ShoppingBag className="size-10" aria-hidden="true" />}
        action={
          <Link href="/products" className="btn-primary">
            Browse the shop
          </Link>
        }
      >
        Your <Link href="/" className="font-medium text-brand-800 underline">For you</Link> feed is a good place to start.
      </EmptyState>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <section aria-label="Items in your cart" className="card px-4 sm:px-6">
        <ul className="divide-y divide-slate-200">
          {cart.data.items.map((line) => (
            <Line key={line.product.id} line={line} />
          ))}
        </ul>
      </section>
      <aside aria-label="Order summary" className="card h-fit space-y-4 p-6">
        <h2 className="text-lg font-semibold">Order summary</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-600">Items</dt>
            <dd>{pluralize(cart.data.item_count, "item")}</dd>
          </div>
          <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold">
            <dt>Subtotal</dt>
            <dd className="tabular-nums">{formatPrice(cart.data.subtotal)}</dd>
          </div>
        </dl>
        <button
          type="button"
          className="btn-primary w-full py-3"
          disabled={placeOrder.isPending}
          onClick={() =>
            placeOrder.mutate(undefined, { onSuccess: (order) => router.push(`/orders/${order.id}?placed=1`) })
          }
        >
          {placeOrder.isPending ? "Placing order…" : "Place order"}
        </button>
        <p className="text-xs text-slate-500">Demo store: the order is recorded but no payment is taken.</p>
        {placeOrder.error ? (
          <p role="alert" className="text-sm text-rose-700">
            {placeOrder.error instanceof ApiError ? placeOrder.error.message : "Couldn't place your order."}
          </p>
        ) : null}
      </aside>
    </div>
  );
}

export default function CartPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Your cart</h1>
      <RequireAuth what="your cart">
        <CartContents />
      </RequireAuth>
    </div>
  );
}
