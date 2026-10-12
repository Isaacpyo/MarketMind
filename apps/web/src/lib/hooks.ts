"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "@/lib/api/client";
import type {
  AdminOverview,
  AlsParams,
  Cart,
  Category,
  EventIn,
  Order,
  Product,
  ProductPage,
  Recommendation,
  RecommendationList,
  TrainingRun,
} from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import type { CatalogParams } from "@/lib/catalog-params";

export const PAGE_SIZE = 24;

// --- catalogue (public) ----------------------------------------------------------------------

export function useProducts(params: CatalogParams) {
  return useQuery({
    queryKey: ["products", params],
    queryFn: ({ signal }) =>
      api<ProductPage>("/products", {
        signal,
        query: { ...params, category: params.category || undefined, q: params.q || undefined, page_size: PAGE_SIZE },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: ({ signal }) => api<Category[]>("/categories", { signal }),
    staleTime: 10 * 60_000,
  });
}

export function useProduct(id: string) {
  return useQuery({
    queryKey: ["product", id],
    queryFn: ({ signal }) => api<Product>(`/products/${encodeURIComponent(id)}`, { signal }),
  });
}

export function useSimilar(id: string) {
  return useQuery({
    queryKey: ["product", id, "similar"],
    queryFn: ({ signal }) => api<Recommendation[]>(`/products/${encodeURIComponent(id)}/similar`, { signal }),
  });
}

export function useAlsoBought(id: string) {
  return useQuery({
    queryKey: ["product", id, "also-bought"],
    queryFn: ({ signal }) => api<Recommendation[]>(`/products/${encodeURIComponent(id)}/also-bought`, { signal }),
  });
}

export function useTrending(category?: string) {
  return useQuery({
    queryKey: ["trending", category ?? null],
    queryFn: ({ signal }) =>
      api<Recommendation[]>("/recommendations/trending", { signal, query: { category, limit: 12 } }),
  });
}

// --- shopper (authenticated) -----------------------------------------------------------------

export function useForYou() {
  const { status, user } = useAuth();
  return useQuery({
    queryKey: ["user", "for-you", user?.id],
    queryFn: ({ signal }) => api<RecommendationList>("/recommendations/for-you", { signal, query: { limit: 12 } }),
    enabled: status === "authenticated",
    staleTime: 0,
  });
}

export function useCart() {
  const { status, user } = useAuth();
  return useQuery({
    queryKey: ["user", "cart", user?.id],
    queryFn: ({ signal }) => api<Cart>("/cart", { signal }),
    enabled: status === "authenticated",
  });
}

export function useOrders() {
  const { status, user } = useAuth();
  return useQuery({
    queryKey: ["user", "orders", user?.id],
    queryFn: ({ signal }) => api<Order[]>("/orders", { signal }),
    enabled: status === "authenticated",
  });
}

export function useOrder(id: string) {
  const { status, user } = useAuth();
  return useQuery({
    queryKey: ["user", "order", user?.id, id],
    queryFn: ({ signal }) => api<Order>(`/orders/${encodeURIComponent(id)}`, { signal }),
    enabled: status === "authenticated",
  });
}

function useCartMutation<TVars>(fn: (vars: TVars) => Promise<Cart>) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  return useMutation({
    mutationFn: fn,
    onSuccess: (cart) => {
      queryClient.setQueryData(["user", "cart", user?.id], cart);
      // Cart contents are excluded from the feed, and add-to-cart is a strong signal.
      void queryClient.invalidateQueries({ queryKey: ["user", "for-you"] });
    },
  });
}

export function useAddToCart() {
  return useCartMutation((vars: { productId: string; quantity?: number }) =>
    api<Cart>("/cart/items", { method: "POST", body: { product_id: vars.productId, quantity: vars.quantity ?? 1 } }),
  );
}

export function useSetQuantity() {
  return useCartMutation((vars: { productId: string; quantity: number }) =>
    api<Cart>(`/cart/items/${encodeURIComponent(vars.productId)}`, { method: "PUT", body: { quantity: vars.quantity } }),
  );
}

export function useRemoveFromCart() {
  return useCartMutation((productId: string) =>
    api<Cart>(`/cart/items/${encodeURIComponent(productId)}`, { method: "DELETE" }),
  );
}

export function usePlaceOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api<Order>("/orders", { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["user"] });
    },
  });
}

/** Fire-and-forget implicit feedback. Failures are ignored: tracking must never break a page. */
export function useTrackEvent() {
  const queryClient = useQueryClient();
  const { status } = useAuth();
  return useCallback(
    (event: EventIn) => {
      if (status !== "authenticated") return;
      api("/events", { method: "POST", body: event, keepalive: true, timeoutMs: 15_000 })
        .then(() => queryClient.invalidateQueries({ queryKey: ["user", "for-you"] }))
        .catch(() => undefined);
    },
    [queryClient, status],
  );
}

// --- admin -----------------------------------------------------------------------------------

const TRAINING_POLL_MS = 2000;

/** Polls while a training run is in progress, then stops by itself. */
export function useAdminOverview(enabled: boolean) {
  return useQuery({
    queryKey: ["user", "admin", "overview"],
    queryFn: ({ signal }) => api<AdminOverview>("/admin/overview", { signal }),
    enabled,
    refetchInterval: (query) => (query.state.data?.latest_run?.status === "running" ? TRAINING_POLL_MS : false),
  });
}

export function useTrainingRuns(enabled: boolean) {
  return useQuery({
    queryKey: ["user", "admin", "runs"],
    queryFn: ({ signal }) => api<TrainingRun[]>("/admin/runs", { signal, query: { limit: 8 } }),
    enabled,
    refetchInterval: (query) =>
      query.state.data?.some((run) => run.status === "running") ? TRAINING_POLL_MS : false,
  });
}

export function useRetrain() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: AlsParams) => api<TrainingRun>("/admin/retrain", { method: "POST", body: params }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["user", "admin"] });
    },
  });
}
