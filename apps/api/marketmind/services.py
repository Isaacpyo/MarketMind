"""Shared helpers that turn Mongo documents into API models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from marketmind.config import Settings
from marketmind.db import Db
from marketmind.recsys.interactions import UserProfile, aggregate_user_events
from marketmind.schemas import AuthOut, Product, User
from marketmind.security import create_access_token


def to_product(doc: Mapping[str, Any]) -> Product:
    return Product(
        id=str(doc["_id"]),
        title=str(doc["title"]),
        description=str(doc.get("description", "")),
        category=str(doc["category"]),
        price=float(doc["price"]),
        popularity=int(doc.get("popularity", 0)),
    )


def to_user(doc: Mapping[str, Any]) -> User:
    return User(
        id=str(doc["_id"]),
        email=str(doc["email"]),
        name=str(doc["name"]),
        role=doc.get("role", "customer"),
        is_demo=bool(doc.get("is_demo", False)),
    )


def issue_token(user: Mapping[str, Any], settings: Settings) -> AuthOut:
    token = create_access_token(
        user_id=str(user["_id"]),
        role=user.get("role", "customer"),
        secret=settings.jwt_secret.get_secret_value(),
        ttl_minutes=settings.jwt_ttl_minutes,
    )
    return AuthOut(access_token=token, user=to_user(user))


def products_by_id(db: Db, ids: list[str]) -> dict[str, Product]:
    return {str(doc["_id"]): to_product(doc) for doc in db.products.find({"_id": {"$in": ids}})}


def load_profile(db: Db, user_id: str) -> UserProfile:
    events = db.events.find({"user_id": user_id}, {"_id": 0, "product_id": 1, "type": 1})
    cart = db.carts.find_one({"_id": user_id}) or {}
    return aggregate_user_events(events, (line["product_id"] for line in cart.get("items", [])))
