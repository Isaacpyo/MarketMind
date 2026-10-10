from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from marketmind.deps import CurrentUser, DbDep, EngineDep, RecommenderDep
from marketmind.recsys.hybrid import ScoredItem
from marketmind.recsys.interactions import UserProfile, confidence
from marketmind.schemas import Recommendation, RecommendationList
from marketmind.services import load_profile, products_by_id

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

_VERBS = {
    "purchase": "bought",
    "add_to_cart": "added",
    "rec_click": "liked",
    "view": "viewed",
}


def explain(item: ScoredItem, titles: list[str], product_ids: list[str], profile: UserProfile) -> str:
    """Human-readable reason for a recommendation, shown on every card."""
    if item.source == "als":
        return "Popular with shoppers who share your taste"
    if item.source == "content" and item.anchor is not None and item.anchor >= 0:
        verb = _VERBS.get(profile.strongest.get(product_ids[item.anchor], "view"), "viewed")
        return f"Because you {verb} “{titles[item.anchor]}”"
    return "Trending with shoppers right now"


@router.get("/for-you", response_model=RecommendationList)
def for_you(
    user: CurrentUser,
    db: DbDep,
    engine: EngineDep,
    recommender: RecommenderDep,
    limit: Annotated[int, Query(ge=1, le=48)] = 12,
) -> RecommendationList:
    """Personalised feed. The user vector is recomputed from live events on every call."""
    profile = load_profile(db, str(user["_id"]))
    catalog = recommender.catalog
    history = [catalog.index[pid] for pid in profile.weights if pid in catalog.index]
    values = [profile.weights[catalog.product_ids[i]] for i in history]
    exclude = [catalog.index[pid] for pid in profile.exclude if pid in catalog.index]
    # Same compression as training: log1p of the summed event weights.
    result = recommender.recommend(history, list(confidence(values)), limit, exclude=exclude)
    ids = [catalog.product_ids[item.index] for item in result.items]
    products = products_by_id(db, ids)
    model = engine.model
    return RecommendationList(
        strategy=result.strategy,
        model_version=model.version if model and result.strategy == "hybrid" else None,
        items=[
            Recommendation(
                product=products[pid],
                score=round(item.score, 4),
                reason=explain(item, catalog.titles, catalog.product_ids, profile),
                source=item.source,
            )
            for pid, item in zip(ids, result.items, strict=True)
            if pid in products
        ],
    )


@router.get("/trending", response_model=list[Recommendation])
def trending(
    db: DbDep,
    recommender: RecommenderDep,
    category: Annotated[str | None, Query(max_length=60)] = None,
    limit: Annotated[int, Query(ge=1, le=48)] = 12,
) -> list[Recommendation]:
    """Most-bought products (distinct shoppers), optionally within a category."""
    items = recommender.trending(limit, category=category)
    catalog = recommender.catalog
    ids = [catalog.product_ids[item.index] for item in items]
    products = products_by_id(db, ids)
    reason = f"Popular in {category}" if category else "Trending with shoppers right now"
    return [
        Recommendation(product=products[pid], score=round(item.score, 4), reason=reason, source="popularity")
        for pid, item in zip(ids, items, strict=True)
        if pid in products
    ]
