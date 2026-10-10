"""Build the committed seed files from the UCI Online Retail dataset.

Usage (from apps/api):
    uv run --group seed python scripts/build_seed.py

Source: Daqing Chen, "Online Retail", UCI Machine Learning Repository (CC BY 4.0),
https://doi.org/10.24432/C5BW33

Outputs (data/seed/):
    products.json         ~1,000 most-bought products with derived title/category/price
    interactions.csv.gz   one purchase per (customer, product), first-purchase timestamp
    demo_profile.json     a real customer's history, cloned for each "Try the demo" login
"""

from __future__ import annotations

import gzip
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketmind.catalog_rules import categorize, describe, prettify_title  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
SEED_DIR = ROOT / "data" / "seed"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"

N_PRODUCTS = 1000
N_CUSTOMERS = 3000
MIN_ITEMS_PER_CUSTOMER = 5
RANDOM_SEED = 7


def load_raw() -> pd.DataFrame:
    xlsx = RAW_DIR / "online_retail.xlsx"
    if not xlsx.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        archive = RAW_DIR / "online_retail.zip"
        print(f"Downloading {SOURCE_URL} …")
        urllib.request.urlretrieve(SOURCE_URL, archive)  # noqa: S310 - fixed https URL
        with zipfile.ZipFile(archive) as zf:
            zf.extract("Online Retail.xlsx", RAW_DIR)
        (RAW_DIR / "Online Retail.xlsx").rename(xlsx)
    print("Reading spreadsheet (takes ~30s) …")
    return pd.read_excel(xlsx, dtype={"StockCode": str, "InvoiceNo": str})


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[
        df["CustomerID"].notna()
        & (df["Quantity"] > 0)
        & (df["UnitPrice"] > 0)
        & ~df["InvoiceNo"].str.startswith("C")  # cancellations
        & df["StockCode"].str.match(r"^\d{5}[A-Z]?$")  # drop postage, fees, manual lines
        & df["Description"].notna()
    ].copy()
    df["CustomerID"] = df["CustomerID"].astype(int).astype(str)
    df["Description"] = df["Description"].astype(str).str.strip()
    return df


def build_products(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    buyers = df.groupby("StockCode")["CustomerID"].nunique().sort_values(ascending=False)
    top_skus = set(buyers.index[:N_PRODUCTS])
    df = df[df["StockCode"].isin(top_skus)]

    products: list[dict[str, object]] = []
    for sku, group in df.groupby("StockCode"):
        raw = group["Description"].mode().iloc[0]
        title = prettify_title(raw)
        category = categorize(raw)
        products.append(
            {
                "sku": sku,
                "title": title,
                "category": category,
                "description": describe(title, category),
                "price": round(float(group["UnitPrice"].median()), 2),
                "buyers": int(buyers[sku]),
            }
        )
    products.sort(key=lambda p: (-int(p["buyers"]), str(p["sku"])))  # type: ignore[call-overload]
    for p in products:
        del p["buyers"]
    return df, products


def build_interactions(df: pd.DataFrame) -> pd.DataFrame:
    pairs = (
        df.groupby(["CustomerID", "StockCode"])["InvoiceDate"]
        .min()
        .reset_index()
        .rename(columns={"CustomerID": "customer_id", "StockCode": "sku", "InvoiceDate": "ts"})
    )
    counts = pairs.groupby("customer_id").size()
    eligible = np.array(sorted(counts[counts >= MIN_ITEMS_PER_CUSTOMER].index))
    rng = np.random.default_rng(RANDOM_SEED)
    chosen = set(rng.choice(eligible, size=min(N_CUSTOMERS, len(eligible)), replace=False))
    pairs = pairs[pairs["customer_id"].isin(chosen)]
    return pairs.sort_values(["customer_id", "ts", "sku"]).reset_index(drop=True)


def pick_demo_profile(df: pd.DataFrame, pairs: pd.DataFrame) -> dict[str, object]:
    """Pick a real customer with a mid-sized, multi-order history as the demo template."""
    stats = pairs.groupby("customer_id").agg(items=("sku", "size"))
    invoices = df.groupby("CustomerID")["InvoiceNo"].nunique()
    stats["invoices"] = invoices.reindex(stats.index).fillna(0).astype(int)
    candidates = stats[(stats["items"].between(25, 45)) & (stats["invoices"].between(3, 6))]
    candidates = candidates.assign(dist=(candidates["items"] - 35).abs()).sort_values(["dist"])
    customer_id = str(candidates.index[0])

    history = df[df["CustomerID"] == customer_id]
    orders = []
    for invoice, lines in history.groupby("InvoiceNo"):
        orders.append(
            {
                "invoice": str(invoice),
                "ts": lines["InvoiceDate"].min().isoformat(),
                "lines": [
                    {
                        "sku": row.StockCode,
                        # Wholesale quantities (e.g. 48) are clipped to shopper-sized ones.
                        "qty": int(min(max(row.Quantity, 1), 6)),
                        "unit_price": round(float(row.UnitPrice), 2),
                    }
                    for row in lines.itertuples()
                ],
            }
        )
    orders.sort(key=lambda o: str(o["ts"]))
    return {"customer_id": customer_id, "orders": orders}


def main() -> None:
    df = clean(load_raw())
    df, products = build_products(df)
    pairs = build_interactions(df)
    known = set(pairs["sku"])
    products = [p for p in products if p["sku"] in known]
    df = df[df["StockCode"].isin(known)]
    demo = pick_demo_profile(df, pairs)

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    (SEED_DIR / "products.json").write_text(json.dumps(products, indent=1, ensure_ascii=False))
    with gzip.open(SEED_DIR / "interactions.csv.gz", "wt", encoding="utf-8") as fh:
        out = pairs.assign(ts=pairs["ts"].dt.strftime("%Y-%m-%dT%H:%M:%S"))
        out.to_csv(fh, index=False)
    (SEED_DIR / "demo_profile.json").write_text(json.dumps(demo, indent=1))

    cats = pd.Series([p["category"] for p in products]).value_counts()
    print(f"products={len(products)} customers={pairs['customer_id'].nunique()} interactions={len(pairs)}")
    print(f"demo customer={demo['customer_id']} orders={len(demo['orders'])}")  # type: ignore[arg-type]
    print(cats.to_string())


if __name__ == "__main__":
    main()
