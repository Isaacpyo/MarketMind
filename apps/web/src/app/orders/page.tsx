"use client";

import { ChevronRight, Receipt } from "lucide-react";
import Link from "next/link";
import { RequireAuth } from "@/components/RequireAuth";
import { EmptyState, ErrorState, Spinner } from "@/components/States";
import { ApiError } from "@/lib/api/client";
import { formatDate, formatPrice, pluralize } from "@/lib/format";
import { useOrders } from "@/lib/hooks";

function OrderList() {
  const orders = useOrders();
  if (orders.isPending) {
    return (
      <div className="py-16 text-center">
        <Spinner label="Loading your orders" />
      </div>
    );
  }
  if (orders.error) {
    return <ErrorState message={orders.error instanceof ApiError ? orders.error.message : "Couldn't load orders."} onRetry={() => void orders.refetch()} />;
  }
  if (orders.data.length === 0) {
    return (
      <EmptyState
        title="No orders yet"
        icon={<Receipt className="size-10" aria-hidden="true" />}
        action={
          <Link href="/products" className="btn-primary">
            Start shopping
          </Link>
        }
      >
        Orders you place appear here, and they feed straight back into your recommendations.
      </EmptyState>
    );
  }
  return (
    <ul className="space-y-3">
      {orders.data.map((order) => {
        const units = order.lines.reduce((sum, l) => sum + l.quantity, 0);
        return (
          <li key={order.id}>
            <Link href={`/orders/${order.id}`} className="card flex items-center gap-4 p-4 transition hover:shadow-md">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-900">
                  Order placed {formatDate(order.created_at)}
                  <span className="ml-2 text-sm font-normal text-slate-500">#{order.id.slice(-6)}</span>
                </p>
                <p className="mt-0.5 truncate text-sm text-slate-600">
                  {pluralize(units, "item")}: {order.lines.slice(0, 3).map((l) => l.title).join(", ")}
                  {order.lines.length > 3 ? ` and ${order.lines.length - 3} more` : ""}
                </p>
              </div>
              <p className="font-semibold tabular-nums">{formatPrice(order.total)}</p>
              <ChevronRight className="size-5 text-slate-400" aria-hidden="true" />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export default function OrdersPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Your orders</h1>
      <RequireAuth what="your orders">
        <OrderList />
      </RequireAuth>
    </div>
  );
}
