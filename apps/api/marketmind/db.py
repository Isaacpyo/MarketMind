"""MongoDB connection and index management."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

Document = dict[str, Any]
Db = Database[Document]


def connect(uri: str, db_name: str) -> tuple[MongoClient[Document], Db]:
    client: MongoClient[Document] = MongoClient(
        uri,
        serverSelectionTimeoutMS=10_000,
        appname="marketmind-api",
        tz_aware=True,
    )
    return client, client[db_name]


def ensure_indexes(db: Db) -> None:
    """Idempotently create the indexes the app relies on."""
    db.users.create_index("email", unique=True)
    # TTL indexes: only documents that carry `expires_at` (demo shoppers' data) are removed.
    for name in ("users", "events", "carts", "orders"):
        db[name].create_index("expires_at", expireAfterSeconds=0)

    db.events.create_index([("user_id", ASCENDING), ("ts", DESCENDING)])
    db.events.create_index([("source", ASCENDING), ("ts", DESCENDING)])
    db.orders.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.products.create_index([("category", ASCENDING), ("popularity", DESCENDING)])
    db.products.create_index([("popularity", DESCENDING)])
    db.training_runs.create_index([("started_at", DESCENDING)])
