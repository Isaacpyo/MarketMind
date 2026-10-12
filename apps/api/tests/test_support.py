"""Tests for the small supporting modules: config, security, rate limits, catalogue rules, seed."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import jwt
import pytest
from pydantic import ValidationError

from marketmind.catalog_rules import FALLBACK_CATEGORY, categorize, prettify_title
from marketmind.config import DEFAULT_SEED_DIR, Settings
from marketmind.db import Db
from marketmind.ratelimit import RateLimiter
from marketmind.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from marketmind.seed import is_seeded, seed_database
from marketmind.timeutil import utcnow

# --- config ----------------------------------------------------------------------------------


def test_cors_origins_parse_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://shop.example.com/, http://localhost:3000")
    assert Settings().cors_origins == ["https://shop.example.com", "http://localhost:3000"]


def test_production_requires_a_real_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret="too-short")
    assert Settings(app_env="production", jwt_secret="x" * 40).app_env == "production"


# --- security --------------------------------------------------------------------------------


def test_password_hashing_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_long_passwords_are_fully_significant() -> None:
    base = "a" * 80
    hashed = hash_password(base + "1")
    assert not verify_password(base + "2", hashed), "bcrypt alone would ignore bytes past 72"


def test_tokens_round_trip_and_reject_tampering() -> None:
    token = create_access_token(user_id="abc", role="admin", secret="s" * 32, ttl_minutes=5)
    claims = decode_access_token(token, "s" * 32)
    assert claims["sub"] == "abc"
    assert claims["role"] == "admin"
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token, "t" * 32)
    expired = create_access_token(user_id="abc", role="customer", secret="s" * 32, ttl_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired, "s" * 32)


# --- rate limiter ----------------------------------------------------------------------------


def test_rate_limiter_sliding_window() -> None:
    limiter = RateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("ip", now=0)
    assert limiter.allow("ip", now=1)
    assert not limiter.allow("ip", now=2)
    assert limiter.allow("other", now=2), "keys are independent"
    assert limiter.allow("ip", now=10.5), "old hits slide out of the window"


# --- catalogue rules -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("WHITE HANGING HEART T-LIGHT HOLDER ", "White Hanging Heart T-Light Holder"),
        ("SET OF 3 CAKE TINS PANTRY DESIGN ", "Set of 3 Cake Tins Pantry Design"),
        ("WOOD S/3 CABINET ANT WHITE FINISH", "Wood Set of 3 Cabinet Antique White Finish"),
        ("KEY FOB , SHED", "Key Fob, Shed"),
        ("ENGLISH ROSE NOTEBOOK A7 SIZE", "English Rose Notebook A7 Size"),
    ],
)
def test_prettify_title(raw: str, expected: str) -> None:
    assert prettify_title(raw) == expected


@pytest.mark.parametrize(
    ("raw", "category"),
    [
        ("JUMBO BAG RED RETROSPOT", "Bags"),
        ("PACK OF 72 RETROSPOT CAKE CASES", "Kitchen & Dining"),
        ("PAPER CHAIN KIT 50'S CHRISTMAS ", "Christmas & Seasonal"),
        ("WHITE HANGING HEART T-LIGHT HOLDER", "Candles & Lighting"),
        ("SET OF 20 KIDS COOKIE CUTTERS", "Kitchen & Dining"),
        ("TINY THING", FALLBACK_CATEGORY),  # "TIN" must not match inside "TINY"
    ],
)
def test_categorize(raw: str, category: str) -> None:
    assert categorize(raw) == category


# --- seed ------------------------------------------------------------------------------------


def test_committed_seed_files_are_consistent() -> None:
    products = json.loads((DEFAULT_SEED_DIR / "products.json").read_text("utf-8"))
    skus = {p["sku"] for p in products}
    assert len(skus) == len(products) == 1000
    assert all(p["price"] > 0 and p["title"] and p["category"] for p in products)
    with gzip.open(DEFAULT_SEED_DIR / "interactions.csv.gz", "rt", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) > 100_000
    assert {r["sku"] for r in rows} <= skus
    demo = json.loads((DEFAULT_SEED_DIR / "demo_profile.json").read_text("utf-8"))
    demo_rows = [r for r in rows if r["customer_id"] == demo["customer_id"]]
    assert len(demo_rows) >= 20, "the demo shopper needs enough history for a hybrid feed"
    assert {line["sku"] for o in demo["orders"] for line in o["lines"]} <= skus


def test_seeding_is_idempotent_and_shifts_dates(db: Db, seed_dir: Path) -> None:
    assert seed_database(db, seed_dir) is True
    assert is_seeded(db)
    assert seed_database(db, seed_dir) is False
    assert db.products.count_documents({}) == 40
    newest = db.events.find_one(sort=[("ts", -1)])
    assert newest is not None
    meta = db.meta.find_one({"_id": "seed"})
    assert meta is not None
    assert (meta["seeded_at"] - newest["ts"]).days == 1, "history should end yesterday"
    # Product popularity = number of distinct customers who bought it.
    top = db.products.find_one(sort=[("popularity", -1)])
    assert top is not None
    assert top["popularity"] == len(db.events.distinct("user_id", {"product_id": top["_id"]}))


def test_seeding_skips_when_another_process_holds_the_lock(db: Db, seed_dir: Path) -> None:
    db.meta.insert_one({"_id": "seed_lock", "at": utcnow()})
    assert seed_database(db, seed_dir) is False
    assert db.products.count_documents({}) == 0
