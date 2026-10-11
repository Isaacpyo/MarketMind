"use client";

import { CircleCheck, Lock, Minus, Plus, ShoppingCart, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { DemoButton } from "@/components/DemoButton";
import { ProductArt } from "@/components/ProductArt";
import { RecommendationRail } from "@/components/RecommendationRail";
import { EmptyState, ErrorState, Spinner } from "@/components/States";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { formatPrice } from "@/lib/format";
import { useAddToCart, useAlsoBought, useProduct, useSimilar, useTrackEvent } from "@/lib/hooks";

function AddToCart({ productId }: { productId: string }) {
  const { status } = useAuth();
  const add = useAddToCart();
  const [quantity, setQuantity] = useState(1);
  const qtyId = useId();

  if (status === "anonymous") {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-4">
        <p className="flex items-center gap-2 text-sm text-slate-700">
          <Lock className="size-4" aria-hidden="true" /> Sign in to add items to your cart.
        </p>
        <div className="mt-3 flex flex-wrap items-start gap-3">
          <DemoButton redirectTo={`/products/${productId}`} />
          <Link href={`/login?next=/products/${productId}`} className="btn-secondary">
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor={qtyId} className="label">
            Quantity
          </label>
          <div className="flex items-center rounded-lg border border-slate-300 bg-white">
            <button
              type="button"
              className="p-2.5 text-slate-700 hover:bg-slate-100 disabled:opacity-40"
              onClick={() => setQuantity((q) => Math.max(1, q - 1))}
              disabled={quantity <= 1}
              aria-label="Decrease quantity"
            >
              <Minus className="size-4" aria-hidden="true" />
            </button>
            <input
              id={qtyId}
              type="number"
              inputMode="numeric"
              min={1}
              max={20}
              value={quantity}
              onChange={(e) => setQuantity(Math.min(20, Math.max(1, Number(e.target.value) || 1)))}
              className="w-12 border-x border-slate-300 py-2 text-center text-sm [appearance:textfield] focus:outline-none [&::-webkit-inner-spin-button]:appearance-none"
            />
            <button
              type="button"
              className="p-2.5 text-slate-700 hover:bg-slate-100 disabled:opacity-40"
              onClick={() => setQuantity((q) => Math.min(20, q + 1))}
              disabled={quantity >= 20}
              aria-label="Increase quantity"
            >
              <Plus className="size-4" aria-hidden="true" />
            </button>
          </div>
        </div>
        <button
          type="button"
          className="btn-primary px-5 py-3"
          disabled={add.isPending || status !== "authenticated"}
          onClick={() => add.mutate({ productId, quantity })}
        >
          <ShoppingCart className="size-4" aria-hidden="true" />
          {add.isPending ? "Adding…" : "Add to cart"}
        </button>
      </div>
      <div aria-live="polite">
        {add.isSuccess ? (
          <p className="flex items-center gap-2 text-sm text-emerald-700">
            <CircleCheck className="size-4" aria-hidden="true" /> Added to your cart.{" "}
            <Link href="/cart" className="font-semibold underline underline-offset-2">
              View cart
            </Link>
          </p>
        ) : null}
        {add.error ? (
          <p role="alert" className="text-sm text-rose-700">
            {add.error instanceof ApiError ? add.error.message : "Couldn't add this item."}
          </p>
        ) : null}
      </div>
    </div>
  );
}

export default function ProductPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { status } = useAuth();
  const product = useProduct(id);
  const similar = useSimilar(id);
  const alsoBought = useAlsoBought(id);
  const track = useTrackEvent();
  const tracked = useRef<string | null>(null);

  // One view event per product page visit (the API also de-duplicates within 30 minutes).
  useEffect(() => {
    if (status === "authenticated" && product.data && tracked.current !== id) {
      tracked.current = id;
      track({ product_id: id, type: "view" });
    }
  }, [id, product.data, status, track]);

  if (product.isPending) {
    return (
      <div className="py-16 text-center">
        <Spinner label="Loading product" />
      </div>
    );
  }
  if (product.error) {
    if (product.error instanceof ApiError && (product.error.status === 404 || product.error.status === 422)) {
      return (
        <EmptyState
          title="Product not found"
          action={
            <Link href="/products" className="btn-secondary">
              Back to the shop
            </Link>
          }
        >
          It may have been removed from the catalogue.
        </EmptyState>
      );
    }
    return <ErrorState message={product.error.message} onRetry={() => void product.refetch()} />;
  }

  const p = product.data;
  return (
    <div className="space-y-12">
      <nav aria-label="Breadcrumb" className="text-sm text-slate-600">
        <ol className="flex flex-wrap items-center gap-1.5">
          <li>
            <Link href="/products" className="hover:text-brand-800 hover:underline">
              Shop
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li>
            <Link href={`/products?category=${encodeURIComponent(p.category)}`} className="hover:text-brand-800 hover:underline">
              {p.category}
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page" className="truncate text-slate-900">
            {p.title}
          </li>
        </ol>
      </nav>

      <article className="grid gap-6 md:grid-cols-2 md:gap-10">
        <ProductArt
          productId={p.id}
          category={p.category}
          size="lg"
          className="card mx-auto w-full max-w-sm rounded-2xl md:max-w-none"
        />
        <div className="space-y-5">
          <div>
            <p className="text-sm font-medium uppercase tracking-wide text-brand-800">{p.category}</p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{p.title}</h1>
            <p className="mt-3 text-2xl font-semibold">{formatPrice(p.price)}</p>
          </div>
          <p className="flex items-center gap-2 text-sm text-slate-600">
            <Users className="size-4" aria-hidden="true" />
            Bought by {p.popularity.toLocaleString("en-GB")} shoppers
          </p>
          <p className="text-slate-700">{p.description}</p>
          <AddToCart productId={p.id} />
          <p className="text-xs text-slate-500">SKU {p.id} · Demo store: no payment is taken at checkout.</p>
        </div>
      </article>

      <RecommendationRail
        id="similar"
        title="Similar items"
        description="Content-based: TF-IDF cosine similarity on product names."
        items={similar.data}
        isPending={similar.isPending}
        error={similar.error}
        onRetry={() => void similar.refetch()}
        context="similar"
      />
      <RecommendationRail
        id="also-bought"
        title="Customers also bought"
        description="Collaborative: neighbours in the ALS item-factor space."
        items={alsoBought.data}
        isPending={alsoBought.isPending}
        error={alsoBought.error}
        onRetry={() => void alsoBought.refetch()}
        context="also_bought"
      />
    </div>
  );
}
