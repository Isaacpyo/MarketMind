from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, status
from pymongo import ASCENDING, DESCENDING

from marketmind.deps import DbDep, RecommenderDep
from marketmind.recsys.hybrid import HybridRecommender, ScoredItem
from marketmind.schemas import Category, Product, ProductPage, Recommendation, SortOption
from marketmind.services import products_by_id, to_product

router = APIRouter(tags=["catalogue"])

ProductIdPath = Annotated[str, Path(pattern=r"^[0-9]{5}[A-Z]?$")]
Limit = Annotated[int, Query(ge=1, le=24)]

_SORTS: dict[str, list[tuple[str, int]]] = {
    "popular": [("popularity", DESCENDING), ("_id", ASCENDING)],
    "price_asc": [("price", ASCENDING), ("_id", ASCENDING)],
    "price_desc": [("price", DESCENDING), ("_id", ASCENDING)],
    "name": [("title", ASCENDING), ("_id", ASCENDING)],
}


@router.get("/products", response_model=ProductPage)
def list_products(
    db: DbDep,
    q: Annotated[str | None, Query(max_length=80)] = None,
    category: Annotated[str | None, Query(max_length=60)] = None,
    sort: SortOption = "popular",
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    page_size: Annotated[int, Query(ge=1, le=60)] = 24,
) -> ProductPage:
    query: dict[str, Any] = {}
    if q and q.strip():
        # Every word must appear somewhere in the title; input is escaped, so no regex injection.
        query["$and"] = [{"title": {"$regex": re.escape(word), "$options": "i"}} for word in q.split()[:6]]
    if category:
        query["category"] = category
    total = db.products.count_documents(query)
    cursor = db.products.find(query).sort(_SORTS[sort]).skip((page - 1) * page_size).limit(page_size)
    return ProductPage(items=[to_product(doc) for doc in cursor], total=total, page=page, page_size=page_size)


@router.get("/categories", response_model=list[Category])
def list_categories(db: DbDep) -> list[Category]:
    rows = db.products.aggregate(
        [{"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"count": -1, "_id": 1}}]
    )
    return [Category(name=str(r["_id"]), count=int(r["count"])) for r in rows]


@router.get("/products/{product_id}", response_model=Product)
def get_product(product_id: ProductIdPath, db: DbDep) -> Product:
    doc = db.products.find_one({"_id": product_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return to_product(doc)


def _catalog_index(recommender: HybridRecommender, product_id: str) -> int:
    index = recommender.catalog.index.get(product_id)
    if index is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return index


def _to_recommendations(
    db: DbDep, recommender: HybridRecommender, items: list[ScoredItem], reason: str
) -> list[Recommendation]:
    ids = [recommender.catalog.product_ids[item.index] for item in items]
    products = products_by_id(db, ids)
    return [
        Recommendation(product=products[pid], score=round(item.score, 4), reason=reason, source=item.source)
        for pid, item in zip(ids, items, strict=True)
        if pid in products
    ]


@router.get("/products/{product_id}/similar", response_model=list[Recommendation])
def similar_products(
    product_id: ProductIdPath, db: DbDep, recommender: RecommenderDep, limit: Limit = 8
) -> list[Recommendation]:
    """Content-based neighbours: TF-IDF cosine similarity on product text."""
    items = recommender.similar_items(_catalog_index(recommender, product_id), limit)
    return _to_recommendations(db, recommender, items, "Similar name and style")


@router.get("/products/{product_id}/also-bought", response_model=list[Recommendation])
def also_bought(
    product_id: ProductIdPath, db: DbDep, recommender: RecommenderDep, limit: Limit = 8
) -> list[Recommendation]:
    """Collaborative neighbours: cosine similarity of ALS item factors."""
    items = recommender.also_bought(_catalog_index(recommender, product_id), limit)
    reason = (
        "Often bought by the same shoppers"
        if items and items[0].source == "als"
        else "Similar name and style"
    )
    return _to_recommendations(db, recommender, items, reason)
