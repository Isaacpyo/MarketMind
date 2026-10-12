"""Shared fixtures: a small synthetic shop with clear taste clusters, served from mongomock."""

from __future__ import annotations

import gzip
import json
import random
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import mongomock
import pytest
from fastapi.testclient import TestClient
from pymongo import UpdateOne

from marketmind.config import Settings
from marketmind.db import Db
from marketmind.main import create_app

THEMES = ["Red Retrospot", "Blue Polkadot", "Vintage Paisley", "Woodland Animal"]
ITEM_TYPES = [
    "Mug",
    "Lunch Bag",
    "Cake Cases",
    "Notebook",
    "Tea Towel",
    "Gift Wrap",
    "Cushion",
    "Bunting",
    "Storage Tin",
    "Candle",
]
CATEGORY_OF = {
    "Mug": "Kitchen & Dining",
    "Lunch Bag": "Bags",
    "Cake Cases": "Kitchen & Dining",
    "Notebook": "Stationery & Gift Wrap",
    "Tea Towel": "Kitchen & Dining",
    "Gift Wrap": "Stationery & Gift Wrap",
    "Cushion": "Home Décor",
    "Bunting": "Toys, Crafts & Party",
    "Storage Tin": "Storage & Organisation",
    "Candle": "Candles & Lighting",
}


def _patch_mongomock_bulk_write() -> None:
    """mongomock's bulk_write predates pymongo 4.11's UpdateOne(sort=...) signature."""

    def bulk_write(self: Any, requests: list[Any], ordered: bool = True, **_: Any) -> None:
        for request in requests:
            if not isinstance(request, UpdateOne):
                raise NotImplementedError(type(request))
            doc = request._doc
            self.update_one(request._filter, doc, upsert=bool(request._upsert))

    mongomock.Collection.bulk_write = bulk_write  # type: ignore[method-assign,assignment]


_patch_mongomock_bulk_write()


def synthetic_products() -> list[dict[str, Any]]:
    products = []
    for t, theme in enumerate(THEMES):
        for i, item in enumerate(ITEM_TYPES):
            sku = f"{10000 + t * 100 + i}"
            products.append(
                {
                    "sku": sku,
                    "title": f"{theme} {item}",
                    "category": CATEGORY_OF[item],
                    "description": f"{theme} {item}, a test product.",
                    "price": round(1.0 + i * 0.75, 2),
                }
            )
    return products


def synthetic_interactions(n_customers: int = 80, seed: int = 3) -> list[tuple[str, str, str]]:
    """Each customer loves one theme: ~85% of their purchases come from it."""
    rng = random.Random(seed)
    products = synthetic_products()
    by_theme = {theme: [p["sku"] for p in products if p["title"].startswith(theme)] for theme in THEMES}
    start = datetime(2011, 1, 1, tzinfo=UTC)
    rows = []
    for c in range(n_customers):
        customer = str(20000 + c)
        theme = THEMES[c % len(THEMES)]
        owned = set(rng.sample(by_theme[theme], 7))
        other = [p["sku"] for p in products if not p["title"].startswith(theme)]
        owned.add(rng.choice(other))
        for sku in sorted(owned):
            ts = start + timedelta(days=rng.randint(0, 300), minutes=rng.randint(0, 600))
            rows.append((customer, sku, ts.strftime("%Y-%m-%dT%H:%M:%S")))
    return rows


def write_seed_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    products = synthetic_products()
    rows = synthetic_interactions()
    (path / "products.json").write_text(json.dumps(products))
    with gzip.open(path / "interactions.csv.gz", "wt", encoding="utf-8") as fh:
        fh.write("customer_id,sku,ts\n")
        for row in rows:
            fh.write(",".join(row) + "\n")
    demo_customer = rows[0][0]
    demo_skus = [sku for customer, sku, _ in rows if customer == demo_customer][:3]
    (path / "demo_profile.json").write_text(
        json.dumps(
            {
                "customer_id": demo_customer,
                "orders": [
                    {
                        "invoice": "500001",
                        "ts": "2011-06-01T10:00:00",
                        "lines": [{"sku": sku, "qty": 2, "unit_price": 1.5} for sku in demo_skus],
                    }
                ],
            }
        )
    )
    return path


@pytest.fixture(autouse=True)
def _ignore_local_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not depend on a developer's apps/api/.env (the README has you create one)."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture
def seed_dir(tmp_path: Path) -> Path:
    return write_seed_dir(tmp_path / "seed")


@pytest.fixture
def settings(seed_dir: Path) -> Settings:
    return Settings(
        app_env="test",
        seed_dir=seed_dir,
        jwt_secret="test-secret-test-secret-test-secret!",
        retrain_cooldown_seconds=0,
        auth_rate_limit_per_minute=1000,
        cors_origins="http://localhost:3000",
    )


@pytest.fixture
def db() -> Db:
    client: mongomock.MongoClient[dict[str, Any]] = mongomock.MongoClient(tz_aware=True)
    database: Db = client["marketmind_test"]
    return database


@pytest.fixture
def client(settings: Settings, db: Db) -> Iterator[TestClient]:
    with TestClient(create_app(settings, db)) as test_client:
        yield test_client


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def demo_token(client: TestClient) -> str:
    response = client.post("/api/auth/demo")
    assert response.status_code == 201
    token: str = response.json()["access_token"]
    return token


@pytest.fixture
def customer_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": "ada@example.com", "password": "correct horse battery", "name": "Ada"},
    )
    assert response.status_code == 201
    token: str = response.json()["access_token"]
    return token
