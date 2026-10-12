import type { SortOption } from "@/lib/api/types";

export const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "popular", label: "Most popular" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "name", label: "Name A–Z" },
];

export interface CatalogParams {
  q: string;
  category: string;
  sort: SortOption;
  page: number;
}

const SORTS = new Set<string>(SORT_OPTIONS.map((o) => o.value));

/** Read catalogue filters from the URL, ignoring anything malformed. */
export function parseCatalogParams(search: URLSearchParams): CatalogParams {
  const sort = search.get("sort") ?? "popular";
  const page = Number.parseInt(search.get("page") ?? "1", 10);
  return {
    q: (search.get("q") ?? "").slice(0, 80),
    category: (search.get("category") ?? "").slice(0, 60),
    sort: (SORTS.has(sort) ? sort : "popular") as SortOption,
    page: Number.isFinite(page) && page >= 1 && page <= 500 ? page : 1,
  };
}

/** Serialise filters back to a query string, omitting defaults to keep URLs short. */
export function toCatalogQuery(params: Partial<CatalogParams>): string {
  const search = new URLSearchParams();
  if (params.q?.trim()) search.set("q", params.q.trim());
  if (params.category) search.set("category", params.category);
  if (params.sort && params.sort !== "popular") search.set("sort", params.sort);
  if (params.page && params.page > 1) search.set("page", String(params.page));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}
