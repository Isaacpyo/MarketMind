import { CloudOff, LoaderCircle, PackageOpen, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-slate-600">
      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
      <span>{label}…</span>
    </span>
  );
}

export function SkeletonGrid({ count = 6, label = "Loading products" }: { count?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 xl:grid-cols-6">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card animate-pulse overflow-hidden">
          <div className="aspect-square bg-slate-200" />
          <div className="space-y-2 p-3">
            <div className="h-3 w-4/5 rounded bg-slate-200" />
            <div className="h-3 w-1/3 rounded bg-slate-200" />
          </div>
        </div>
      ))}
      <span className="sr-only">{label}…</span>
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
  icon,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="card flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 text-slate-400">{icon ?? <PackageOpen className="size-10" aria-hidden="true" />}</div>
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      {children ? <div className="mt-1 max-w-md text-sm text-slate-600">{children}</div> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="card flex flex-col items-center px-6 py-10 text-center">
      <CloudOff className="mb-3 size-10 text-rose-400" aria-hidden="true" />
      <h2 className="text-lg font-semibold text-slate-900">Something went wrong</h2>
      <p className="mt-1 max-w-md text-sm text-slate-600">{message}</p>
      {onRetry ? (
        <button type="button" className="btn-secondary mt-5" onClick={onRetry}>
          <RefreshCw className="size-4" aria-hidden="true" /> Try again
        </button>
      ) : null}
    </div>
  );
}
