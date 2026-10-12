"""One-click demo shoppers.

Each "Try the demo" click creates an isolated shopper whose history is cloned from a
real Online Retail customer. Visitors never see each other's carts, and everything a
demo shopper creates carries `expires_at` so MongoDB's TTL index cleans it up.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from bson import ObjectId

from marketmind.config import Settings
from marketmind.db import Db
from marketmind.seed import CUSTOMER_PREFIX, read_demo_profile, seed_time_shift
from marketmind.timeutil import as_utc, utcnow


def create_demo_user(db: Db, settings: Settings) -> dict[str, Any]:
    now = utcnow()
    expires_at = now + timedelta(hours=settings.demo_ttl_hours)
    user_id = ObjectId()
    user = {
        "_id": user_id,
        "email": f"demo-{secrets.token_hex(4)}@demo.marketmind.dev",
        "name": "Demo Shopper",
        "password_hash": None,
        "role": "admin" if settings.demo_users_are_admin else "customer",
        "is_demo": True,
        "created_at": now,
        "expires_at": expires_at,
    }
    db.users.insert_one(user)
    uid = str(user_id)

    profile = read_demo_profile(settings.seed_dir)
    template = db.events.find(
        {"user_id": CUSTOMER_PREFIX + profile.customer_id, "source": "seed"},
        {"_id": 0, "product_id": 1, "type": 1, "ts": 1},
    )
    clones = [
        {
            "user_id": uid,
            "product_id": e["product_id"],
            "type": e["type"],
            "ts": as_utc(e["ts"]),
            "source": "demo_clone",
            "expires_at": expires_at,
        }
        for e in template
    ]
    if clones:
        db.events.insert_many(clones)

    shift = seed_time_shift(db)
    titles = {
        str(p["_id"]): str(p["title"])
        for p in db.products.find(
            {"_id": {"$in": [line["sku"] for o in profile.orders for line in o["lines"]]}},
            {"title": 1},
        )
    }
    orders = []
    for order in profile.orders:
        lines = [
            {
                "product_id": line["sku"],
                "title": titles[line["sku"]],
                "unit_price": float(line["unit_price"]),
                "quantity": int(line["qty"]),
                "line_total": round(float(line["unit_price"]) * int(line["qty"]), 2),
            }
            for line in order["lines"]
            if line["sku"] in titles
        ]
        if not lines:
            continue
        orders.append(
            {
                "user_id": uid,
                "created_at": as_utc(datetime.fromisoformat(order["ts"])) + shift,
                "status": "placed",
                "lines": lines,
                "total": round(sum(line["line_total"] for line in lines), 2),
                "expires_at": expires_at,
            }
        )
    if orders:
        db.orders.insert_many(orders)
    return user
