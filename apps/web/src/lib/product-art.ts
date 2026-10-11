/**
 * The Online Retail dataset has no product photos, so each product gets a generated
 * tile: a category colour and icon, with a per-product variation so neighbours differ.
 */

export type ArtIcon =
  | "utensils"
  | "home"
  | "pen"
  | "party"
  | "tree"
  | "archive"
  | "bag"
  | "flame"
  | "flower"
  | "bath"
  | "gem"
  | "gift";

const CATEGORY_ART: Record<string, { hue: number; icon: ArtIcon }> = {
  "Kitchen & Dining": { hue: 18, icon: "utensils" },
  "Home Décor": { hue: 262, icon: "home" },
  "Stationery & Gift Wrap": { hue: 210, icon: "pen" },
  "Toys, Crafts & Party": { hue: 330, icon: "party" },
  "Christmas & Seasonal": { hue: 140, icon: "tree" },
  "Storage & Organisation": { hue: 190, icon: "archive" },
  Bags: { hue: 35, icon: "bag" },
  "Candles & Lighting": { hue: 45, icon: "flame" },
  "Garden & Outdoor": { hue: 100, icon: "flower" },
  "Bath & Beauty": { hue: 175, icon: "bath" },
  "Fashion & Accessories": { hue: 295, icon: "gem" },
};
const FALLBACK = { hue: 230, icon: "gift" as ArtIcon };

/** FNV-1a: tiny, stable string hash. */
export function hashString(value: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

export interface ProductArt {
  icon: ArtIcon;
  background: string;
  foreground: string;
  /** Pattern rotation in degrees. */
  angle: number;
}

export function productArt(productId: string, category: string): ProductArt {
  const base = CATEGORY_ART[category] ?? FALLBACK;
  const hash = hashString(productId);
  const hue = (base.hue + ((hash % 31) - 15) + 360) % 360;
  const angle = (hash >>> 5) % 180;
  return {
    icon: base.icon,
    background: `linear-gradient(${angle}deg, hsl(${hue} 85% 94%), hsl(${(hue + 25) % 360} 70% 86%))`,
    foreground: `hsl(${hue} 55% 32%)`,
    angle,
  };
}
