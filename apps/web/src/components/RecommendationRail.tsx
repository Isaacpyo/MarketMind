"use client";

import type { ReactNode } from "react";
import type { EventIn, Recommendation } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import { useTrackEvent } from "@/lib/hooks";
import { ProductCard } from "@/components/ProductCard";
import { EmptyState, ErrorState, SkeletonGrid } from "@/components/States";

interface RailProps {
  id: string;
  title: string;
  description?: ReactNode;
  badge?: ReactNode;
  items: Recommendation[] | undefined;
  isPending: boolean;
  error: unknown;
  onRetry?: () => void;
  context: NonNullable<EventIn["context"]>;
  emptyMessage?: string;
  skeletonCount?: number;
}

/** A titled grid of recommendations. Clicks are reported back as implicit feedback. */
export function RecommendationRail({
  id,
  title,
  description,
  badge,
  items,
  isPending,
  error,
  onRetry,
  context,
  emptyMessage = "Nothing to show here yet.",
  skeletonCount = 6,
}: RailProps) {
  const track = useTrackEvent();
  return (
    <section aria-labelledby={`${id}-title`} className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id={`${id}-title`} className="text-xl font-semibold tracking-tight text-slate-900">
            {title}
          </h2>
          {description ? <p className="mt-0.5 text-sm text-slate-600">{description}</p> : null}
        </div>
        {badge}
      </div>
      {isPending ? (
        <SkeletonGrid count={skeletonCount} label={`Loading ${title.toLowerCase()}`} />
      ) : error ? (
        <ErrorState message={error instanceof ApiError ? error.message : "Couldn't load these products."} onRetry={onRetry} />
      ) : !items || items.length === 0 ? (
        <EmptyState title="No suggestions yet">{emptyMessage}</EmptyState>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 xl:grid-cols-6">
          {items.map((item) => (
            <li key={item.product.id} className="flex">
              <ProductCard
                product={item.product}
                recommendation={item}
                onSelect={() => track({ product_id: item.product.id, type: "rec_click", context })}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
