from __future__ import annotations

from typing import Annotated, Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Path, Query, status
from pymongo import DESCENDING

from marketmind.deps import CurrentUser, DbDep
from marketmind.routers.cart import render_cart
from marketmind.schemas import Order, OrderLine
from marketmind.timeutil import as_utc, utcnow

router = APIRouter(prefix="/orders", tags=["orders"])


def to_order(doc: dict[str, Any]) -> Order:
    return Order(
        id=str(doc["_id"]),
        created_at=as_utc(doc["created_at"]),
        status=doc["status"],
        lines=[OrderLine(**line) for line in doc["lines"]],
        total=float(doc["total"]),
    )


@router.post("", response_model=Order, status_code=status.HTTP_201_CREATED)
def place_order(user: CurrentUser, db: DbDep) -> Order:
    """Check out the cart. Demo store: an order is recorded, no payment is taken."""
    user_id = str(user["_id"])
    cart = render_cart(db, user_id)
    if not cart.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your cart is empty")

    now = utcnow()
    expires = {"expires_at": user["expires_at"]} if user.get("expires_at") else {}
    order = {
        "_id": ObjectId(),
        "user_id": user_id,
        "created_at": now,
        "status": "placed",
        # Snapshot titles and prices: later catalogue edits must not rewrite history.
        "lines": [
            {
                "product_id": line.product.id,
                "title": line.product.title,
                "unit_price": line.product.price,
                "quantity": line.quantity,
                "line_total": line.line_total,
            }
            for line in cart.items
        ],
        "total": cart.subtotal,
        **expires,
    }
    db.orders.insert_one(order)
    db.events.insert_many(
        [
            {
                "user_id": user_id,
                "product_id": line.product.id,
                "type": "purchase",
                "ts": now,
                "source": "live",
                **expires,
            }
            for line in cart.items
        ]
    )
    db.carts.update_one({"_id": user_id}, {"$set": {"items": [], "updated_at": now}})
    return to_order(order)


@router.get("", response_model=list[Order])
def list_orders(user: CurrentUser, db: DbDep, limit: Annotated[int, Query(ge=1, le=50)] = 20) -> list[Order]:
    cursor = db.orders.find({"user_id": str(user["_id"])}).sort("created_at", DESCENDING).limit(limit)
    return [to_order(doc) for doc in cursor]


@router.get("/{order_id}", response_model=Order)
def get_order(
    order_id: Annotated[str, Path(pattern=r"^[0-9a-f]{24}$")], user: CurrentUser, db: DbDep
) -> Order:
    try:
        oid = ObjectId(order_id)
    except InvalidId as exc:  # pragma: no cover - guarded by the path pattern
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    doc = db.orders.find_one({"_id": oid, "user_id": str(user["_id"])})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return to_order(doc)
