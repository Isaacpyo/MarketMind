import {
  Archive,
  Bath,
  Flame,
  Flower2,
  Gem,
  Gift,
  House,
  PartyPopper,
  PenLine,
  ShoppingBag,
  TreePine,
  UtensilsCrossed,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";
import { productArt, type ArtIcon } from "@/lib/product-art";

const ICONS: Record<ArtIcon, LucideIcon> = {
  utensils: UtensilsCrossed,
  home: House,
  pen: PenLine,
  party: PartyPopper,
  tree: TreePine,
  archive: Archive,
  bag: ShoppingBag,
  flame: Flame,
  flower: Flower2,
  bath: Bath,
  gem: Gem,
  gift: Gift,
};

/** Decorative generated artwork (the dataset has no product photos). */
export function ProductArt({
  productId,
  category,
  size = "md",
  className,
}: {
  productId: string;
  category: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const art = productArt(productId, category);
  const Icon = ICONS[art.icon];
  const iconSize = { sm: 28, md: 40, lg: 88 }[size];
  return (
    <div
      aria-hidden="true"
      className={clsx("relative flex aspect-square items-center justify-center overflow-hidden", className)}
      style={{ background: art.background, color: art.foreground }}
    >
      <div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage: "radial-gradient(currentColor 1px, transparent 1.5px)",
          backgroundSize: "14px 14px",
          transform: `rotate(${art.angle}deg) scale(1.5)`,
        }}
      />
      <Icon size={iconSize} strokeWidth={1.5} className="relative drop-shadow-sm" />
    </div>
  );
}
