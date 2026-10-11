import { describe, expect, it } from "vitest";
import { parseCatalogParams, toCatalogQuery } from "@/lib/catalog-params";
import { formatDuration, formatPercent, formatPrice, pluralize } from "@/lib/format";
import { liftOverPopularity, metricRows, niceMax } from "@/lib/metrics";
import { safeNext } from "@/lib/navigation";
import { hashString, productArt } from "@/lib/product-art";
import { validateParams } from "@/components/admin/RetrainForm";

describe("catalogue params", () => {
  it("parses and sanitises URL params", () => {
    expect(parseCatalogParams(new URLSearchParams("q=mug&category=Bags&sort=price_asc&page=3"))).toEqual({
      q: "mug",
      category: "Bags",
      sort: "price_asc",
      page: 3,
    });
    expect(parseCatalogParams(new URLSearchParams("sort=random&page=-2"))).toEqual({
      q: "",
      category: "",
      sort: "popular",
      page: 1,
    });
  });

  it("round-trips while omitting defaults", () => {
    expect(toCatalogQuery({ q: " mug ", sort: "popular", page: 1 })).toBe("?q=mug");
    expect(toCatalogQuery({ category: "Home Décor", sort: "name", page: 2 })).toBe(
      "?category=Home+D%C3%A9cor&sort=name&page=2",
    );
    expect(toCatalogQuery({})).toBe("");
  });
});

describe("formatting", () => {
  it("formats GBP, percentages, counts and durations", () => {
    expect(formatPrice(2.95)).toBe("£2.95");
    expect(formatPercent(0.0681)).toBe("6.8%");
    expect(pluralize(1, "item")).toBe("1 item");
    expect(pluralize(1200, "product")).toBe("1,200 products");
    expect(formatDuration(5.4)).toBe("5s");
    expect(formatDuration(65)).toBe("1m 05s");
  });
});

describe("product art", () => {
  it("is deterministic and category-aware", () => {
    expect(hashString("85123A")).toBe(hashString("85123A"));
    expect(productArt("85123A", "Candles & Lighting")).toEqual(productArt("85123A", "Candles & Lighting"));
    expect(productArt("85123A", "Candles & Lighting").icon).toBe("flame");
    expect(productArt("85123A", "Unknown").icon).toBe("gift");
    expect(productArt("1", "Bags").background).not.toBe(productArt("2", "Bags").background);
  });
});

describe("metrics helpers", () => {
  const models = {
    hybrid: { precision: 0.068, recall: 0.14, coverage: 0.88 },
    popularity: { precision: 0.0226, recall: 0.046, coverage: 0.06 },
    als: { precision: 0.057, recall: 0.128, coverage: 0.84 },
  };

  it("orders rows consistently and skips missing models", () => {
    expect(metricRows(models, "precision").map((r) => r.model)).toEqual(["popularity", "als", "hybrid"]);
  });

  it("computes lift over the popularity baseline", () => {
    expect(liftOverPopularity(models)).toBeCloseTo(3.0, 1);
    expect(liftOverPopularity({ hybrid: models.hybrid })).toBeNull();
  });

  it("picks nice axis maxima", () => {
    expect(niceMax(0.068)).toBe(0.1);
    expect(niceMax(0.14)).toBe(0.2);
    expect(niceMax(0.88)).toBe(1);
    expect(niceMax(0)).toBe(1);
  });
});

describe("safeNext", () => {
  it("only allows same-site relative paths", () => {
    expect(safeNext("/products/85123A")).toBe("/products/85123A");
    expect(safeNext("https://evil.example")).toBe("/");
    expect(safeNext("//evil.example")).toBe("/");
    expect(safeNext("/\\evil.example")).toBe("/");
    expect(safeNext(null)).toBe("/");
  });
});

describe("retrain form validation", () => {
  const valid = { factors: "64", regularization: "0.05", alpha: "1", iterations: "20", hybrid_weight: "0.5" };

  it("accepts the defaults", () => {
    expect(validateParams(valid)).toEqual({});
  });

  it("mirrors the API's bounds", () => {
    expect(validateParams({ ...valid, factors: "4096", iterations: "2.5", alpha: "", hybrid_weight: "abc" })).toEqual({
      factors: "Between 8 and 256",
      iterations: "Whole numbers only",
      alpha: "Enter a number",
      hybrid_weight: "Enter a number",
    });
  });
});
