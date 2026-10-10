from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, status

from marketmind.db import Db
from marketmind.deps import CurrentUser, DbDep
from marketmind.schemas import Cart, CartAddIn, CartLine, CartSetIn
from marketmind.services import products_by_id
from marketmind.timeutil import utcnow

router = APIRouter(prefix="/cart", tags=["cart"])

ProductIdPath = Annotated[str, Path(pattern=r"^[0-9]{5}[A-Z]?$")]
MAX_LINES = 50
MAX_QUANTITY = 20


def _load_items(db: Db, user_id: str) -> list[dict[str, Any]]:
    cart = db.carts.find_one({"_id": user_id}) or {}
    return list(cart.get("items", []))


def _save_items(db: Db, user: dict[str, Any], items: list[dict[str, Any]]) -> None:
    update: dict[str, Any] = {"items": items, "updated_at": utcnow()}
    if user.get("expires_at"):
        update["expires_at"] = user["expires_at"]
    db.carts.update_one({"_id": str(user["_id"])}, {"$set": update}, upsert=True)


def render_cart(db: Db, user_id: str) -> Cart:
    items = _load_items(db, user_id)
    products = products_by_id(db, [line["product_id"] for line in items])
    lines = [
        CartLine(
            product=products[line["product_id"]],
            quantity=int(line["quantity"]),
            line_total=round(products[line["product_id"]].price * int(line["quantity"]), 2),
        )
        for line in items
        if line["product_id"] in products
    ]
    return Cart(
        items=lines,
        item_count=sum(line.quantity for line in lines),
        subtotal=round(sum(line.line_total for line in lines), 2),
    )


def _record_add_to_cart(db: Db, user: dict[str, Any], product_id: str) -> None:
    event: dict[str, Any] = {
        "user_id": str(user["_id"]),
        "product_id": product_id,
        "type": "add_to_cart",
        "ts": utcnow(),
        "source": "live",
    }
    if user.get("expires_at"):
        event["expires_at"] = user["expires_at"]
    db.events.insert_one(event)


@router.get("", response_model=Cart)
def get_cart(user: CurrentUser, db: DbDep) -> Cart:
    return render_cart(db, str(user["_id"]))


@router.post("/items", response_model=Cart)
def add_item(body: CartAddIn, user: CurrentUser, db: DbDep) -> Cart:
    if db.products.count_documents({"_id": body.product_id}, limit=1) == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    items = _load_items(db, str(user["_id"]))
    line = next((i for i in items if i["product_id"] == body.product_id), None)
    if line is None:
        if len(items) >= MAX_LINES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your cart is full")
        items.append({"product_id": body.product_id, "quantity": body.quantity})
    else:
        line["quantity"] = min(MAX_QUANTITY, int(line["quantity"]) + body.quantity)
    _save_items(db, user, items)
    _record_add_to_cart(db, user, body.product_id)
    return render_cart(db, str(user["_id"]))


@router.put("/items/{product_id}", response_model=Cart)
def set_quantity(product_id: ProductIdPath, body: CartSetIn, user: CurrentUser, db: DbDep) -> Cart:
    items = _load_items(db, str(user["_id"]))
    line = next((i for i in items if i["product_id"] == product_id), None)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That item isn't in your cart")
    line["quantity"] = body.quantity
    _save_items(db, user, items)
    return render_cart(db, str(user["_id"]))


@router.delete("/items/{product_id}", response_model=Cart)
def remove_item(product_id: ProductIdPath, user: CurrentUser, db: DbDep) -> Cart:
    items = [i for i in _load_items(db, str(user["_id"])) if i["product_id"] != product_id]
    _save_items(db, user, items)
    return render_cart(db, str(user["_id"]))
