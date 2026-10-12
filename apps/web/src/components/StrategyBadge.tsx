import clsx from "clsx";
import type { Strategy } from "@/lib/api/types";

const LABELS: Record<Strategy, { text: string; tone: string }> = {
  popularity: { text: "Trending picks · browse to personalise", tone: "bg-slate-100 text-slate-700 ring-slate-200" },
  cold_start: { text: "Getting to know you · content + popularity", tone: "bg-amber-50 text-amber-900 ring-amber-200" },
  hybrid: { text: "Personalised · ALS + content hybrid", tone: "bg-brand-50 text-brand-800 ring-brand-200" },
};

export function StrategyBadge({ strategy }: { strategy: Strategy }) {
  const { text, tone } = LABELS[strategy];
  return (
    <span className={clsx("inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset", tone)}>
      {text}
    </span>
  );
}
