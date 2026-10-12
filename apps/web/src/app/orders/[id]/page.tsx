"use client";

import { CircleCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { RequireAuth } from "@/components/RequireAuth";
import { EmptyState, ErrorState, Spinner } from "@/components/States";
import { ApiError } from "@/lib/api/client";
import { formatDateTime, formatPrice } from "@/lib/format";
import { useOrder } from "@/lib/hooks";

function OrderDetail({ id }: { id: string }) {
  const order = useOrder(id);
  const justPlaced = useSearchParams().get("placed") === "1";

  if (order.isPending) {
    return (
      <div className="py-16 text-center">
        <Spinner label="Loading order" />
      </div>
    );
  }
  if (order.error) {
    if (order.error instanceof ApiError && (order.error.status === 404 || order.error.status === 422)) {
      return <EmptyState title="Order not found" action={<Link href="/orders" className="btn-secondary">All orders</Link>} />;
    }
    return <ErrorState message={order.error.message} onRetry={() => void order.refetch()} />;
  }

  const o = order.data;
  return (
    <div className="space-y-6">
      {justPlaced ? (
        <div role="status" className="card flex flex-col gap-3 border-emerald-200 bg-emerald-50 p-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-center gap-2 font-medium text-emerald-900">
            <CircleCheck className="size-5" aria-hidden="true" /> Thanks! Your order has been placed.
          </p>
          <Link href="/" className="btn-secondary">
            <Sparkles className="size-4" aria-hidden="true" /> See your updated For you feed
          </Link>
        </div>
      ) : null}
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Order #{o.id.slice(-6)}</h1>
        <p className="text-sm text-slate-600">Placed {formatDateTime(o.created_at)}</p>
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[32rem] text-sm">
          <caption className="sr-only">Items in this order</caption>
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">Product</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Price</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Qty</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {o.lines.map((line, i) => (
              <tr key={`${line.product_id}-${i}`}>
                <td className="px-4 py-3">
                  <Link href={`/products/${line.product_id}`} className="font-medium text-slate-900 hover:text-brand-800">
                    {line.title}
                  </Link>
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{formatPrice(line.unit_price)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{line.quantity}</td>
                <td className="px-4 py-3 text-right tabular-nums">{formatPrice(line.line_total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-slate-200 font-semibold">
              <th scope="row" colSpan={3} className="px-4 py-3 text-right">Total</th>
              <td className="px-4 py-3 text-right tabular-nums">{formatPrice(o.total)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <Link href="/orders" className="inline-block text-sm font-medium text-brand-800 hover:underline">
        ← All orders
      </Link>
    </div>
  );
}

export default function OrderPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RequireAuth what="this order">
      <Suspense fallback={<Spinner label="Loading order" />}>
        <OrderDetail id={id} />
      </Suspense>
    </RequireAuth>
  );
}
