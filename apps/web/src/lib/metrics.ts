import type { ModelMetrics } from "@/lib/api/types";

export const MODEL_ORDER = ["popularity", "content", "als", "hybrid"] as const;
export type ModelName = (typeof MODEL_ORDER)[number];

export const MODEL_LABELS: Record<ModelName, string> = {
  popularity: "Popularity",
  content: "Content (TF-IDF)",
  als: "ALS",
  hybrid: "Hybrid (served)",
};

export const METRICS = [
  { key: "precision", label: "Precision@10", help: "Share of the top 10 that the shopper went on to buy." },
  { key: "recall", label: "Recall@10", help: "Share of held-out purchases found in the top 10." },
  { key: "coverage", label: "Catalogue coverage", help: "Share of products recommended to at least one shopper." },
] as const;
export type MetricKey = (typeof METRICS)[number]["key"];

export interface MetricRow {
  model: ModelName;
  label: string;
  value: number;
}

/** Rows for one metric in a fixed model order, skipping models the run didn't evaluate. */
export function metricRows(models: Record<string, ModelMetrics>, metric: MetricKey): MetricRow[] {
  return MODEL_ORDER.filter((m) => models[m]).map((m) => ({
    model: m,
    label: MODEL_LABELS[m],
    value: models[m]![metric],
  }));
}

/** "3.0×" lift of the served hybrid over the popularity baseline, or null if not computable. */
export function liftOverPopularity(models: Record<string, ModelMetrics>, metric: MetricKey = "precision"): number | null {
  const base = models.popularity?.[metric];
  const hybrid = models.hybrid?.[metric];
  if (base === undefined || hybrid === undefined || base <= 0) return null;
  return hybrid / base;
}

/** A "nice" axis maximum: the smallest of 1/2/2.5/5 × 10^n that covers the value. */
export function niceMax(value: number): number {
  if (value <= 0) return 1;
  const exponent = Math.floor(Math.log10(value));
  const base = 10 ** exponent;
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (step * base >= value) return step * base;
  }
  return 10 * base;
}
