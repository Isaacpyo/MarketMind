"""Load the committed Online Retail seed files into MongoDB (idempotent)."""

from __future__ import annotations

import csv
import gzip
import json
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from pymongo.errors import DuplicateKeyError

from marketmind.db import Db
from marketmind.timeutil import as_utc, utcnow

log = logging.getLogger(__name__)

SEED_VERSION = "online-retail-v1"
CUSTOMER_PREFIX = "c_"
BATCH_SIZE = 5000


@dataclass(frozen=True)
class DemoProfile:
    customer_id: str
    orders: list[dict[str, Any]]


def read_products(seed_dir: Path) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = json.loads((seed_dir / "products.json").read_text("utf-8"))
    return products


def iter_interactions(seed_dir: Path) -> Iterator[tuple[str, str, datetime]]:
    with gzip.open(seed_dir / "interactions.csv.gz", "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield row["customer_id"], row["sku"], as_utc(datetime.fromisoformat(row["ts"]))


@lru_cache(maxsize=4)
def read_demo_profile(seed_dir: Path) -> DemoProfile:
    raw = json.loads((seed_dir / "demo_profile.json").read_text("utf-8"))
    return DemoProfile(customer_id=str(raw["customer_id"]), orders=list(raw["orders"]))


def is_seeded(db: Db) -> bool:
    meta = db.meta.find_one({"_id": "seed"})
    return bool(meta and meta.get("version") == SEED_VERSION and meta.get("complete"))


def seed_time_shift(db: Db) -> timedelta:
    meta = db.meta.find_one({"_id": "seed"}) or {}
    return timedelta(seconds=float(meta.get("ts_shift_seconds", 0.0)))


def seed_database(db: Db, seed_dir: Path, now: datetime | None = None) -> bool:
    """Insert products and historical purchases. Returns True if it seeded anything.

    Timestamps are shifted so the newest historical purchase lands one day before
    seeding: the demo then reads like a live shop instead of a 2011 archive.
    """
    if is_seeded(db):
        return False
    # A lock older than this belongs to a process that died mid-seed.
    db.meta.delete_one({"_id": "seed_lock", "at": {"$lt": utcnow() - timedelta(minutes=10)}})
    try:
        db.meta.insert_one({"_id": "seed_lock", "at": utcnow()})
    except DuplicateKeyError:
        log.info("another process is seeding; skipping")
        return False

    try:
        now = now or utcnow()
        products = read_products(seed_dir)
        rows = list(iter_interactions(seed_dir))
        if not rows:
            raise ValueError("seed interactions are empty")
        shift = (now - timedelta(days=1)) - max(ts for _, _, ts in rows)

        buyers: dict[str, set[str]] = defaultdict(set)
        for customer, sku, _ in rows:
            buyers[sku].add(customer)

        # Start clean in case a previous attempt died half way.
        db.products.delete_many({})
        db.events.delete_many({"source": "seed"})
        db.products.insert_many(
            [
                {
                    "_id": p["sku"],
                    "title": p["title"],
                    "description": p["description"],
                    "category": p["category"],
                    "price": float(p["price"]),
                    "popularity": len(buyers.get(p["sku"], ())),
                }
                for p in products
            ]
        )
        batch: list[dict[str, Any]] = []
        for customer, sku, ts in rows:
            batch.append(
                {
                    "user_id": CUSTOMER_PREFIX + customer,
                    "product_id": sku,
                    "type": "purchase",
                    "ts": ts + shift,
                    "source": "seed",
                }
            )
            if len(batch) >= BATCH_SIZE:
                db.events.insert_many(batch, ordered=False)
                batch = []
        if batch:
            db.events.insert_many(batch, ordered=False)

        db.meta.replace_one(
            {"_id": "seed"},
            {
                "_id": "seed",
                "version": SEED_VERSION,
                "complete": True,
                "seeded_at": now,
                "ts_shift_seconds": shift.total_seconds(),
                "products": len(products),
                "events": len(rows),
            },
            upsert=True,
        )
        log.info("seeded %d products and %d purchase events", len(products), len(rows))
        return True
    finally:
        db.meta.delete_one({"_id": "seed_lock"})
