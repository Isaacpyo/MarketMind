"use client";

import { useState } from "react";
import { formatPercent } from "@/lib/format";
import { niceMax, type MetricRow } from "@/lib/metrics";

const ACCENT = "#6d28d9"; // brand-700: the served model
const MUTED = "#a1a1aa"; // de-emphasis gray for baselines (values are always labelled)

/**
 * Emphasis bar chart: the served hybrid in the accent colour, baselines in gray.
 * One metric per chart (small multiples) so every chart keeps a single axis.
 */
export function MetricBars({ title, help, rows }: { title: string; help: string; rows: MetricRow[] }) {
  const [active, setActive] = useState<MetricRow | null>(null);
  const max = niceMax(Math.max(...rows.map((r) => r.value), 0));
  const baseline = rows.find((r) => r.model === "popularity");

  return (
    <figure className="card flex flex-col p-5">
      <figcaption>
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        <p className="mt-0.5 text-xs text-slate-600">{help}</p>
      </figcaption>
      <ul className="mt-4 space-y-3" onPointerLeave={() => setActive(null)}>
        {rows.map((row) => {
          const width = `${(row.value / max) * 100}%`;
          const lift = baseline && baseline.value > 0 && row !== baseline ? row.value / baseline.value : null;
          return (
            <li
              key={row.model}
              tabIndex={0}
              aria-label={`${row.label}: ${formatPercent(row.value)}${lift ? `, ${lift.toFixed(1)} times popularity` : ""}`}
              onPointerEnter={() => setActive(row)}
              onFocus={() => setActive(row)}
              onBlur={() => setActive(null)}
              className="group -mx-1 rounded-md px-1 py-0.5 outline-offset-1"
            >
              <div className="flex items-baseline justify-between text-xs">
                <span className={row.model === "hybrid" ? "font-semibold text-slate-900" : "text-slate-600"}>
                  {row.label}
                </span>
                <span className="font-medium tabular-nums text-slate-900">{formatPercent(row.value)}</span>
              </div>
              <div className="mt-1 h-3 rounded-r bg-slate-100">
                <div
                  className="h-full rounded-r transition-[filter] group-hover:brightness-110 group-focus:brightness-110"
                  style={{ width, background: row.model === "hybrid" ? ACCENT : MUTED }}
                />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 min-h-5 text-xs text-slate-600" aria-hidden="true">
        {active ? (
          <>
            <strong className="text-slate-900">{formatPercent(active.value, 2)}</strong> {active.label}
            {baseline && active !== baseline && baseline.value > 0
              ? ` · ${(active.value / baseline.value).toFixed(1)}× popularity`
              : ""}
          </>
        ) : (
          <span className="text-slate-400">Hover or focus a bar for detail</span>
        )}
      </p>
    </figure>
  );
}
