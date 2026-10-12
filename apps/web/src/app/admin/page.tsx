"use client";

import { CircleCheck, CircleX, LoaderCircle, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { MetricBars } from "@/components/admin/MetricBars";
import { RetrainForm } from "@/components/admin/RetrainForm";
import { RequireAuth } from "@/components/RequireAuth";
import { EmptyState, ErrorState, Spinner } from "@/components/States";
import { ApiError } from "@/lib/api/client";
import type { AdminOverview, TrainingRun } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { formatDateTime, formatDuration, formatPercent } from "@/lib/format";
import { useAdminOverview, useTrainingRuns } from "@/lib/hooks";
import { METRICS, MODEL_LABELS, MODEL_ORDER, liftOverPopularity, metricRows } from "@/lib/metrics";

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium text-slate-600">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value.toLocaleString("en-GB")}</p>
    </div>
  );
}

function RunStatus({ status }: { status: TrainingRun["status"] }) {
  if (status === "succeeded")
    return (
      <span className="inline-flex items-center gap-1 text-emerald-800">
        <CircleCheck className="size-4" aria-hidden="true" /> Succeeded
      </span>
    );
  if (status === "failed")
    return (
      <span className="inline-flex items-center gap-1 text-rose-800">
        <CircleX className="size-4" aria-hidden="true" /> Failed
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-amber-800">
      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> Running
    </span>
  );
}

function Evaluation({ run }: { run: TrainingRun }) {
  const evaluation = run.evaluation;
  if (!evaluation) return null;
  const lift = liftOverPopularity(evaluation.models);
  const hybrid = evaluation.models.hybrid;
  return (
    <section aria-labelledby="eval-title" className="space-y-4">
      <div>
        <h2 id="eval-title" className="text-xl font-semibold tracking-tight">
          Offline evaluation
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Temporal holdout: for {evaluation.users_evaluated.toLocaleString("en-GB")} shoppers with 5+ items, the
          most recent {formatPercent(evaluation.holdout_fraction, 0)} of their purchases were hidden. Each model,
          trained on the rest, ranks the catalogue; we check its top {evaluation.k}.
        </p>
      </div>
      {hybrid ? (
        <div className="card flex flex-col gap-1 bg-gradient-to-br from-brand-50 to-white p-6">
          <p className="text-sm font-medium text-brand-900">Served model: precision@{evaluation.k}</p>
          <p className="text-5xl font-semibold tracking-tight text-slate-900">{formatPercent(hybrid.precision)}</p>
          {lift ? (
            <p className="text-sm text-slate-700">
              <strong>{lift.toFixed(1)}×</strong> the popularity baseline. Recall@{evaluation.k}{" "}
              {formatPercent(hybrid.recall)}, catalogue coverage {formatPercent(hybrid.coverage, 0)}.
            </p>
          ) : null}
        </div>
      ) : null}
      <div className="grid gap-4 md:grid-cols-3">
        {METRICS.map((m) => (
          <MetricBars key={m.key} title={m.label} help={m.help} rows={metricRows(evaluation.models, m.key)} />
        ))}
      </div>
      <details className="card p-4 text-sm">
        <summary className="cursor-pointer font-medium text-slate-800">Show as a table</summary>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[28rem]">
            <caption className="sr-only">Evaluation metrics per model</caption>
            <thead className="text-left text-slate-600">
              <tr>
                <th scope="col" className="py-2 pr-4 font-medium">Model</th>
                {METRICS.map((m) => (
                  <th key={m.key} scope="col" className="py-2 pr-4 text-right font-medium">
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {MODEL_ORDER.filter((name) => evaluation.models[name]).map((name) => (
                <tr key={name}>
                  <th scope="row" className="py-2 pr-4 text-left font-medium">{MODEL_LABELS[name]}</th>
                  {METRICS.map((m) => (
                    <td key={m.key} className="py-2 pr-4 text-right tabular-nums">
                      {formatPercent(evaluation.models[name]![m.key], 2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

function RunsTable({ runs }: { runs: TrainingRun[] }) {
  return (
    <section aria-labelledby="runs-title" className="card overflow-hidden">
      <h2 id="runs-title" className="border-b border-slate-200 px-5 py-4 text-lg font-semibold">
        Training runs
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-sm">
          <thead className="bg-slate-50 text-left text-slate-600">
            <tr>
              <th scope="col" className="px-5 py-2.5 font-medium">Run</th>
              <th scope="col" className="px-5 py-2.5 font-medium">Started</th>
              <th scope="col" className="px-5 py-2.5 font-medium">Trigger</th>
              <th scope="col" className="px-5 py-2.5 font-medium">Status</th>
              <th scope="col" className="px-5 py-2.5 font-medium">Params</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium">Hybrid P@10</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium">Took</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {runs.map((run) => (
              <tr key={run.id}>
                <td className="px-5 py-3">
                  <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{run.id.slice(-8)}</code>
                </td>
                <td className="whitespace-nowrap px-5 py-3">{formatDateTime(run.started_at)}</td>
                <td className="px-5 py-3 capitalize">{run.trigger}</td>
                <td className="px-5 py-3">
                  <RunStatus status={run.status} />
                  {run.error ? <p className="mt-0.5 max-w-xs truncate text-xs text-rose-700" title={run.error}>{run.error}</p> : null}
                </td>
                <td className="px-5 py-3 text-xs text-slate-600">
                  f={run.params.factors} λ={run.params.regularization} α={run.params.alpha} it={run.params.iterations} w=
                  {run.params.hybrid_weight}
                </td>
                <td className="px-5 py-3 text-right tabular-nums">
                  {run.evaluation?.models.hybrid ? formatPercent(run.evaluation.models.hybrid.precision, 2) : "–"}
                </td>
                <td className="px-5 py-3 text-right tabular-nums">
                  {run.duration_seconds != null ? formatDuration(run.duration_seconds) : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Seconds left until `seconds` after `fetchedAt`, ticking once a second. */
function useCountdown(seconds: number, fetchedAt: number): number {
  const deadline = fetchedAt + seconds * 1000;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (seconds <= 0) return;
    const timer = setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (current >= deadline) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [deadline, seconds]);
  return Math.min(seconds, Math.max(0, Math.ceil((deadline - now) / 1000)));
}

function Dashboard() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const overview = useAdminOverview(isAdmin);
  const runs = useTrainingRuns(isAdmin);
  const running = overview.data?.latest_run?.status === "running" || runs.data?.some((r) => r.status === "running");
  const cooldown = useCountdown(overview.data?.retrain_available_in_seconds ?? 0, overview.dataUpdatedAt);

  if (!isAdmin) {
    return (
      <EmptyState title="Admins only" icon={<ShieldCheck className="size-10" aria-hidden="true" />}>
        This dashboard is for admin accounts. The one-click demo shopper is an admin, so sign out and use “Try the
        demo” to explore it.
      </EmptyState>
    );
  }
  if (overview.isPending) {
    return (
      <div className="py-16 text-center">
        <Spinner label="Loading model metrics" />
      </div>
    );
  }
  if (overview.error) {
    return (
      <ErrorState
        message={overview.error instanceof ApiError ? overview.error.message : "Couldn't load the dashboard."}
        onRetry={() => void overview.refetch()}
      />
    );
  }

  const data: AdminOverview = overview.data;
  const latestSucceeded = runs.data?.find((r) => r.status === "succeeded") ?? null;
  const evalRun = data.latest_run?.status === "succeeded" ? data.latest_run : latestSucceeded;

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Model admin</h1>
          <p className="mt-1 text-sm text-slate-600">
            {data.model ? (
              <>
                Serving model <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{data.model.version.slice(-8)}</code>,
                trained {formatDateTime(data.model.trained_at)} on {data.model.items.toLocaleString("en-GB")} products.
              </>
            ) : (
              "No model trained yet. Recommendations fall back to popularity and content similarity."
            )}
          </p>
        </div>
      </div>

      <section aria-label="Activity" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatTile label="Products" value={data.products} />
        <StatTile label="Registered shoppers" value={data.registered_users} />
        <StatTile label="Demo shoppers" value={data.demo_users} />
        <StatTile label="Live events, last 24h" value={data.live_events_last_24h} />
        <StatTile label="New events since training" value={data.live_events_since_model} />
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="min-w-0 space-y-6">
          {evalRun ? <Evaluation run={evalRun} /> : <EmptyState title="No evaluation yet">Run a training job to see metrics.</EmptyState>}
          {evalRun?.dataset ? (
            <p className="text-sm text-slate-600">
              Dataset: {evalRun.dataset.users.toLocaleString("en-GB")} shoppers ×{" "}
              {evalRun.dataset.items.toLocaleString("en-GB")} products,{" "}
              {evalRun.dataset.interactions.toLocaleString("en-GB")} interactions (
              {evalRun.dataset.train_interactions.toLocaleString("en-GB")} train /{" "}
              {evalRun.dataset.test_interactions.toLocaleString("en-GB")} held out). Events by type:{" "}
              {Object.entries(data.events_by_type)
                .map(([type, n]) => `${type.replace(/_/g, " ")} ${n.toLocaleString("en-GB")}`)
                .join(", ")}
              .
            </p>
          ) : null}
        </div>
        <RetrainForm
          defaults={data.model?.params ?? { factors: 64, regularization: 0.05, alpha: 1, iterations: 20, hybrid_weight: 0.5 }}
          running={Boolean(running)}
          cooldownSeconds={cooldown}
        />
      </div>

      {runs.data && runs.data.length > 0 ? <RunsTable runs={runs.data} /> : null}
    </div>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth what="the model dashboard">
      <Dashboard />
    </RequireAuth>
  );
}
