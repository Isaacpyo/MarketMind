"use client";

import { SearchX, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useId, type FormEvent } from "react";
import { Pagination } from "@/components/Pagination";
import { ProductCard } from "@/components/ProductCard";
import { EmptyState, ErrorState, SkeletonGrid, Spinner } from "@/components/States";
import { ApiError } from "@/lib/api/client";
import type { SortOption } from "@/lib/api/types";
import { SORT_OPTIONS, parseCatalogParams, toCatalogQuery, type CatalogParams } from "@/lib/catalog-params";
import { pluralize } from "@/lib/format";
import { PAGE_SIZE, useCategories, useProducts } from "@/lib/hooks";

function Catalogue() {
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const params = parseCatalogParams(new URLSearchParams(search.toString()));
  const products = useProducts(params);
  const categories = useCategories();
  const ids = { q: useId(), category: useId(), sort: useId() };

  const update = (next: Partial<CatalogParams>) =>
    router.push(`${pathname}${toCatalogQuery({ ...params, page: 1, ...next })}`, { scroll: false });

  function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    update({ q: String(new FormData(event.currentTarget).get("q") ?? "") });
  }

  const totalPages = products.data ? Math.max(1, Math.ceil(products.data.total / PAGE_SIZE)) : 1;
  const heading = params.category || (params.q ? `Results for “${params.q}”` : "All products");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{heading}</h1>
          <p className="mt-1 text-sm text-slate-600" aria-live="polite">
            {products.data ? pluralize(products.data.total, "product") : " "}
            {products.isFetching && products.data ? <span className="ml-2"><Spinner label="Updating" /></span> : null}
          </p>
        </div>
      </div>

      <div className="card grid gap-3 p-4 sm:grid-cols-[1fr_auto_auto] sm:items-end">
        {/* Keyed on the URL value so back/forward navigation resets the uncontrolled input. */}
        <form key={params.q} onSubmit={onSearch} role="search">
          <label htmlFor={ids.q} className="label">
            Search
          </label>
          <div className="flex gap-2">
            <input
              id={ids.q}
              name="q"
              type="search"
              className="input"
              defaultValue={params.q}
              maxLength={80}
              placeholder="e.g. red retrospot"
            />
            <button type="submit" className="btn-primary">
              Search
            </button>
          </div>
        </form>
        <div>
          <label htmlFor={ids.category} className="label">
            Category
          </label>
          <select
            id={ids.category}
            className="input sm:w-56"
            value={params.category}
            onChange={(e) => update({ category: e.target.value })}
          >
            <option value="">All categories</option>
            {categories.data?.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name} ({c.count})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={ids.sort} className="label">
            Sort by
          </label>
          <select
            id={ids.sort}
            className="input sm:w-48"
            value={params.sort}
            onChange={(e) => update({ sort: e.target.value as SortOption })}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {products.isPending ? (
        <SkeletonGrid count={12} />
      ) : products.error ? (
        <ErrorState
          message={products.error instanceof ApiError ? products.error.message : "Couldn't load products."}
          onRetry={() => void products.refetch()}
        />
      ) : products.data.items.length === 0 ? (
        <EmptyState
          title="No products match"
          icon={<SearchX className="size-10" aria-hidden="true" />}
          action={
            <Link href="/products" className="btn-secondary">
              <SlidersHorizontal className="size-4" aria-hidden="true" /> Clear filters
            </Link>
          }
        >
          Try a broader search, such as “bag” or “heart”, or a different category.
        </EmptyState>
      ) : (
        <>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 xl:grid-cols-6">
            {products.data.items.map((p) => (
              <li key={p.id} className="flex">
                <ProductCard product={p} />
              </li>
            ))}
          </ul>
          <Pagination
            page={params.page}
            totalPages={totalPages}
            hrefFor={(page) => `${pathname}${toCatalogQuery({ ...params, page })}`}
          />
        </>
      )}
    </div>
  );
}

export default function ProductsPage() {
  return (
    <Suspense fallback={<SkeletonGrid count={12} />}>
      <Catalogue />
    </Suspense>
  );
}
