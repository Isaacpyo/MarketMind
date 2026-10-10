"""Unit tests for the content, ALS and hybrid recommenders on a synthetic shop."""

from __future__ import annotations

import numpy as np
import pytest

from marketmind.recsys.als import AlsConfig, AlsModel, fit_als
from marketmind.recsys.content import ContentModel, product_text
from marketmind.recsys.hybrid import Catalog, HybridRecommender
from marketmind.recsys.interactions import InteractionData, build_interaction_data
from tests.conftest import THEMES, synthetic_interactions, synthetic_products

PRODUCTS = sorted(synthetic_products(), key=lambda p: p["sku"])
IDS = [p["sku"] for p in PRODUCTS]
TITLES = [p["title"] for p in PRODUCTS]


def theme_of(index: int) -> str:
    return next(t for t in THEMES if TITLES[index].startswith(t))


@pytest.fixture(scope="module")
def data() -> InteractionData:
    rows = [(c, sku, "purchase", float(i)) for i, (c, sku, _) in enumerate(synthetic_interactions())]
    return build_interaction_data(rows, IDS)


@pytest.fixture(scope="module")
def als(data: InteractionData) -> AlsModel:
    # The synthetic shop has four taste clusters, so a rank-4 model captures it exactly.
    config = AlsConfig(factors=4, iterations=15, regularization=0.05, alpha=1.0)
    return AlsModel.from_fitted(fit_als(data.matrix(), config), IDS, config)


@pytest.fixture(scope="module")
def recommender(data: InteractionData, als: AlsModel) -> HybridRecommender:
    popularity = np.bincount(data.items, minlength=len(IDS)).astype(float)
    catalog = Catalog(IDS, TITLES, [p["category"] for p in PRODUCTS], popularity)
    content = ContentModel([product_text(t) for t in TITLES])
    return HybridRecommender(catalog, content, als)


def test_content_model_finds_same_theme_neighbours() -> None:
    content = ContentModel([product_text(t) for t in TITLES])
    mug = TITLES.index("Red Retrospot Mug")
    sims = content.similarity_to(mug)
    assert sims[mug] == pytest.approx(1.0)
    best_other = int(np.argsort(-sims)[1])
    assert TITLES[best_other].startswith("Red Retrospot") or TITLES[best_other].endswith("Mug")


def test_content_profile_and_anchor() -> None:
    content = ContentModel([product_text(t) for t in TITLES])
    history = [TITLES.index("Woodland Animal Mug"), TITLES.index("Woodland Animal Notebook")]
    scores = content.profile_scores(history, [1.0, 1.0])
    ranked = [i for i in np.argsort(-scores) if i not in history][:3]
    assert all(theme_of(int(i)) == "Woodland Animal" for i in ranked)
    tea_towel = TITLES.index("Woodland Animal Tea Towel")
    assert content.anchors([tea_towel], history)[0] in history
    assert content.profile_scores([], []).sum() == 0


def test_content_model_requires_products() -> None:
    with pytest.raises(ValueError, match="at least one product"):
        ContentModel([])


@pytest.mark.parametrize("theme", THEMES)
def test_als_learns_taste_clusters(als: AlsModel, theme: str) -> None:
    history = [TITLES.index(f"{theme} {item}") for item in ("Mug", "Lunch Bag", "Cushion")]
    scores = als.score_user(history, [1.0] * len(history))
    scores[history] = -np.inf
    top5 = np.argsort(-scores)[:5]
    assert sum(theme_of(int(i)) == theme for i in top5) >= 4


def test_als_item_similarity_groups_co_purchased_items(als: AlsModel) -> None:
    item = TITLES.index("Vintage Paisley Candle")
    sims = als.item_similarity(item)
    neighbours = [int(i) for i in np.argsort(-sims)[1:4]]
    assert sum(theme_of(i) == "Vintage Paisley" for i in neighbours) >= 2


def test_als_model_round_trips_through_bytes(als: AlsModel) -> None:
    restored = AlsModel.from_bytes(als.to_bytes(), als.config)
    assert restored.item_ids == als.item_ids
    np.testing.assert_allclose(restored.item_factors, als.item_factors)
    np.testing.assert_allclose(restored.score_user([0, 1], [1.0, 1.0]), als.score_user([0, 1], [1.0, 1.0]))


def test_als_model_rejects_mismatched_shapes() -> None:
    with pytest.raises(ValueError, match="disagree"):
        AlsModel(["a"], np.zeros((2, 4), dtype=np.float32), AlsConfig())


@pytest.mark.parametrize(
    ("n_items", "expected"), [(0, "popularity"), (1, "cold_start"), (2, "cold_start"), (3, "hybrid")]
)
def test_strategy_depends_on_how_much_we_know(
    recommender: HybridRecommender, n_items: int, expected: str
) -> None:
    assert recommender.strategy_for(n_items) == expected


def test_new_shopper_gets_popular_items(recommender: HybridRecommender) -> None:
    result = recommender.recommend([], [], k=5)
    assert result.strategy == "popularity"
    assert [item.source for item in result.items] == ["popularity"] * 5
    top = result.items[0].index
    assert recommender.catalog.popularity[top] == recommender.catalog.popularity.max()


def test_cold_start_blends_content_from_first_view(recommender: HybridRecommender) -> None:
    viewed = TITLES.index("Woodland Animal Bunting")
    result = recommender.recommend([viewed], [1.0], k=4)
    assert result.strategy == "cold_start"
    assert viewed not in [item.index for item in result.items]
    content_items = [item for item in result.items if item.source == "content"]
    assert content_items, "at least one recommendation should be explained by the viewed item"
    assert all(item.anchor == viewed for item in content_items)


def test_warm_shopper_gets_hybrid_feed_without_seen_or_excluded_items(
    recommender: HybridRecommender,
) -> None:
    history = [TITLES.index(f"Red Retrospot {item}") for item in ("Mug", "Lunch Bag", "Notebook", "Candle")]
    excluded = TITLES.index("Red Retrospot Cushion")
    result = recommender.recommend(history, [2.0] * 4, k=5, exclude=[excluded])
    assert result.strategy == "hybrid"
    picked = [item.index for item in result.items]
    assert not set(picked) & {*history, excluded}
    assert sum(theme_of(i) == "Red Retrospot" for i in picked) >= 4
    assert {item.source for item in result.items} <= {"als", "content"}
    scores = [item.score for item in result.items]
    assert scores == sorted(scores, reverse=True)


def test_similar_and_also_bought_exclude_the_product_itself(recommender: HybridRecommender) -> None:
    mug = TITLES.index("Blue Polkadot Mug")
    similar = recommender.similar_items(mug, 5)
    also = recommender.also_bought(mug, 5)
    assert mug not in [i.index for i in similar + also]
    assert {i.source for i in similar} == {"content"}
    assert {i.source for i in also} == {"als"}


def test_also_bought_falls_back_to_content_without_a_model(recommender: HybridRecommender) -> None:
    no_model = HybridRecommender(recommender.catalog, recommender.content, None)
    items = no_model.also_bought(0, 3)
    assert {i.source for i in items} == {"content"}
    # And the feed never claims to be hybrid without ALS.
    assert no_model.strategy_for(10) == "cold_start"


def test_trending_can_be_scoped_to_a_category(recommender: HybridRecommender) -> None:
    items = recommender.trending(20, category="Bags")
    assert items
    assert {recommender.catalog.categories[i.index] for i in items} == {"Bags"}


def test_catalog_validates_column_lengths() -> None:
    with pytest.raises(ValueError, match="equal length"):
        Catalog(["a", "b"], ["A"], ["c", "c"], np.zeros(2))
