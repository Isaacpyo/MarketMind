import { Layers, Sparkles, TrendingUp } from "lucide-react";
import Link from "next/link";
import type { Product, Recommendation } from "@/lib/api/types";
import { formatPrice } from "@/lib/format";
import { ProductArt } from "@/components/ProductArt";

const SOURCE_ICON = { als: Sparkles, content: Layers, popularity: TrendingUp } as const;

export function SourceLabel({ source, reason }: { source: Recommendation["source"]; reason: string }) {
  const Icon = SOURCE_ICON[source];
  return (
    <p className="mt-2 flex items-start gap-1.5 text-xs leading-snug text-brand-800">
      <Icon className="mt-px size-3.5 shrink-0" aria-hidden="true" />
      <span className="line-clamp-2">{reason}</span>
    </p>
  );
}

export function ProductCard({
  product,
  recommendation,
  onSelect,
}: {
  product: Product;
  recommendation?: Pick<Recommendation, "reason" | "source">;
  onSelect?: () => void;
}) {
  return (
    <Link
      href={`/products/${product.id}`}
      onClick={onSelect}
      className="card group flex flex-col overflow-hidden transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <ProductArt productId={product.id} category={product.category} className="transition group-hover:brightness-[1.03]" />
      <div className="flex flex-1 flex-col p-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{product.category}</p>
        <h3 className="mt-0.5 line-clamp-2 text-sm font-medium text-slate-900 group-hover:text-brand-800">
          {product.title}
        </h3>
        <p className="mt-auto pt-2 text-sm font-semibold text-slate-900">{formatPrice(product.price)}</p>
        {recommendation ? <SourceLabel source={recommendation.source} reason={recommendation.reason} /> : null}
      </div>
    </Link>
  );
}
