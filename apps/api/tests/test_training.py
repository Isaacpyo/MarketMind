from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from marketmind.db import Db
from marketmind.engine import RecommenderEngine
from marketmind.recsys.als import AlsConfig
from marketmind.seed import seed_database
from marketmind.training import (
    CooldownActiveError,
    TrainingBusyError,
    TrainingCoordinator,
    load_latest_model,
    train_pipeline,
)
from tests.conftest import synthetic_interactions, synthetic_products

SMALL = AlsConfig(factors=4, iterations=10)


def _products() -> list[dict[str, object]]:
    return [{"_id": p["sku"], "title": p["title"], "category": p["category"]} for p in synthetic_products()]


def _rows() -> list[tuple[str, str, str, float]]:
    return [
        (c, sku, "purchase", datetime.fromisoformat(ts).replace(tzinfo=UTC).timestamp())
        for c, sku, ts in synthetic_interactions()
    ]


def test_train_pipeline_evaluates_every_component_on_a_holdout() -> None:
    output = train_pipeline(_products(), _rows(), SMALL)
    assert set(output.evaluation.models) == {"popularity", "content", "als", "hybrid"}
    assert output.evaluation.users_evaluated == 80
    assert output.dataset.items == 40
    assert output.dataset.train_interactions + output.dataset.test_interactions == output.dataset.interactions
    for metrics in output.evaluation.models.values():
        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 < metrics.coverage <= 1.0
    # Shoppers here have strong themes, so personalisation must beat a global bestseller list.
    models = output.evaluation.models
    assert models["hybrid"].precision > models["popularity"].precision
    assert models["als"].precision > models["popularity"].precision


def test_train_pipeline_counts_distinct_buyers_for_popularity() -> None:
    output = train_pipeline(_products(), _rows(), SMALL)
    assert sum(output.popularity.values()) == len(_rows())


def test_train_pipeline_refuses_tiny_datasets() -> None:
    with pytest.raises(ValueError, match="at least"):
        train_pipeline(_products(), _rows()[:5], SMALL)


@pytest.fixture
def seeded(db: Db, seed_dir: object) -> Db:
    seed_database(db, seed_dir)  # type: ignore[arg-type]
    return db


def test_coordinator_trains_persists_and_hot_swaps_the_model(seeded: Db) -> None:
    engine = RecommenderEngine()
    engine.reload_catalog(seeded)
    coordinator = TrainingCoordinator(seeded, engine, cooldown_seconds=0, threads=1)

    run_id = coordinator.start("admin", SMALL, background=False)

    run = seeded.training_runs.find_one({"_id": run_id})
    assert run is not None
    assert run["status"] == "succeeded"
    assert run["evaluation"]["k"] == 10
    assert engine.model is not None
    assert engine.model.version == run_id
    loaded = load_latest_model(seeded)
    assert loaded is not None
    assert loaded.version == run_id
    assert loaded.als.n_items == 40
    # The lock is released afterwards.
    assert seeded.meta.find_one({"_id": "training_lock"})["run_id"] is None  # type: ignore[index]


def test_coordinator_enforces_cooldown_for_admin_runs(seeded: Db) -> None:
    engine = RecommenderEngine()
    engine.reload_catalog(seeded)
    coordinator = TrainingCoordinator(seeded, engine, cooldown_seconds=300, threads=1)
    coordinator.start("admin", SMALL, background=False)
    with pytest.raises(CooldownActiveError) as excinfo:
        coordinator.start("admin", SMALL, background=False)
    assert 0 < excinfo.value.retry_after <= 300
    # Startup training isn't subject to the admin cooldown.
    assert coordinator.cooldown_remaining("startup") == 0


def test_coordinator_allows_one_run_at_a_time(seeded: Db) -> None:
    coordinator = TrainingCoordinator(seeded, RecommenderEngine(), cooldown_seconds=0, threads=1)
    seeded.meta.insert_one(
        {"_id": "training_lock", "run_id": "someone-else", "acquired_at": datetime.now(UTC)}
    )
    with pytest.raises(TrainingBusyError):
        coordinator.start("admin", SMALL, background=False)


def test_stale_lock_is_taken_over(seeded: Db) -> None:
    engine = RecommenderEngine()
    engine.reload_catalog(seeded)
    coordinator = TrainingCoordinator(seeded, engine, cooldown_seconds=0, threads=1)
    seeded.meta.insert_one(
        {
            "_id": "training_lock",
            "run_id": "crashed",
            "acquired_at": datetime.now(UTC) - timedelta(hours=1),
        }
    )
    run_id = coordinator.start("admin", SMALL, background=False)
    assert seeded.training_runs.find_one({"_id": run_id})["status"] == "succeeded"  # type: ignore[index]


def test_failed_runs_are_recorded(seeded: Db) -> None:
    seeded.events.delete_many({})
    coordinator = TrainingCoordinator(seeded, RecommenderEngine(), cooldown_seconds=0, threads=1)
    run_id = coordinator.start("admin", SMALL, background=False)
    run = seeded.training_runs.find_one({"_id": run_id})
    assert run is not None
    assert run["status"] == "failed"
    assert "at least" in run["error"]


def test_recover_after_restart_fails_orphaned_runs(seeded: Db) -> None:
    seeded.training_runs.insert_one({"_id": "orphan", "status": "running", "started_at": datetime.now(UTC)})
    seeded.meta.insert_one({"_id": "training_lock", "run_id": "orphan", "acquired_at": datetime.now(UTC)})
    TrainingCoordinator(seeded, RecommenderEngine(), cooldown_seconds=0, threads=1).recover_after_restart()
    assert seeded.training_runs.find_one({"_id": "orphan"})["status"] == "failed"  # type: ignore[index]
    assert seeded.meta.find_one({"_id": "training_lock"})["run_id"] is None  # type: ignore[index]


def test_only_recent_artifacts_are_kept(seeded: Db) -> None:
    engine = RecommenderEngine()
    engine.reload_catalog(seeded)
    coordinator = TrainingCoordinator(seeded, engine, cooldown_seconds=0, threads=1)
    for _ in range(4):
        coordinator.start("admin", SMALL, background=False)
    assert seeded.model_artifacts.count_documents({}) == 3
