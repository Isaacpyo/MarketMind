import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

export function Pagination({
  page,
  totalPages,
  hrefFor,
}: {
  page: number;
  totalPages: number;
  hrefFor: (page: number) => string;
}) {
  if (totalPages <= 1) return null;
  const linkClass = "btn-secondary px-3 aria-disabled:pointer-events-none aria-disabled:opacity-50";
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3">
      <Link
        href={hrefFor(page - 1)}
        aria-disabled={page <= 1}
        tabIndex={page <= 1 ? -1 : undefined}
        className={linkClass}
        scroll
      >
        <ChevronLeft className="size-4" aria-hidden="true" /> Previous
      </Link>
      <p className="text-sm text-slate-600" aria-current="page">
        Page {page} of {totalPages}
      </p>
      <Link
        href={hrefFor(page + 1)}
        aria-disabled={page >= totalPages}
        tabIndex={page >= totalPages ? -1 : undefined}
        className={linkClass}
        scroll
      >
        Next <ChevronRight className="size-4" aria-hidden="true" />
      </Link>
    </nav>
  );
}
