"""Training pipeline: Mongo events → holdout evaluation → ALS fit → persisted model."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import numpy as np
from bson import Binary, ObjectId
from pymongo import DESCENDING, UpdateOne
from pymongo.errors import DuplicateKeyError

from marketmind.db import Db
from marketmind.engine import LoadedModel, RecommenderEngine, build_catalog
from marketmind.recsys.als import AlsConfig, AlsModel, fit_als
from marketmind.recsys.content import ContentModel, product_text
from marketmind.recsys.evaluate import Evaluation, evaluate
from marketmind.recsys.hybrid import Catalog, HybridRecommender
from marketmind.recsys.interactions import InteractionData, build_interaction_data
from marketmind.recsys.split import temporal_holdout
from marketmind.timeutil import as_utc, utcnow

log = logging.getLogger(__name__)

Trigger = Literal["startup", "admin"]
EVAL_K = 10
HOLDOUT_FRACTION = 0.2
MIN_INTERACTIONS = 20
STALE_LOCK_AFTER = timedelta(minutes=15)
KEEP_ARTIFACTS = 3
# Copies of the demo template's history would double-count one real customer.
TRAINING_EVENT_FILTER = {"source": {"$ne": "demo_clone"}}


class TrainingBusyError(RuntimeError):
    pass


class CooldownActiveError(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"retrain available in {retry_after}s")
        self.retry_after = retry_after


@dataclass(frozen=True)
class DatasetStats:
    users: int
    items: int
    interactions: int
    train_interactions: int
    test_interactions: int


@dataclass(frozen=True)
class TrainingOutput:
    als: AlsModel
    evaluation: Evaluation
    dataset: DatasetStats
    popularity: dict[str, int]


def distinct_users_per_item(data: InteractionData, mask: np.ndarray | None = None) -> np.ndarray:
    items = data.items if mask is None else data.items[mask]
    return np.bincount(items, minlength=data.n_items).astype(np.float64)


def train_pipeline(
    products: Iterable[Mapping[str, Any]],
    rows: Iterable[tuple[str, str, str, float]],
    config: AlsConfig,
    *,
    threads: int = 1,
    k: int = EVAL_K,
) -> TrainingOutput:
    """Pure training function (no I/O), so it can be unit-tested on synthetic data."""
    catalog = build_catalog(products)
    data = build_interaction_data(rows, catalog.product_ids)
    if len(data) < MIN_INTERACTIONS or data.n_users < 2:
        raise ValueError(f"need at least {MIN_INTERACTIONS} interactions to train, got {len(data)}")

    split = temporal_holdout(data, HOLDOUT_FRACTION)
    train = data.matrix(split.train_mask)
    content = ContentModel([product_text(t) for t in catalog.titles])

    # Popularity for evaluation must come from the training split only (no test leakage).
    eval_catalog = Catalog(
        product_ids=catalog.product_ids,
        titles=catalog.titles,
        categories=catalog.categories,
        popularity=distinct_users_per_item(data, split.train_mask),
    )
    eval_als = AlsModel.from_fitted(fit_als(train, config, threads), catalog.product_ids, config)
    evaluation = evaluate(HybridRecommender(eval_catalog, content, eval_als), train, split.test_items, k=k)

    # The served model is refit on everything we know.
    final_als = AlsModel.from_fitted(fit_als(data.matrix(), config, threads), catalog.product_ids, config)
    counts = distinct_users_per_item(data)
    return TrainingOutput(
        als=final_als,
        evaluation=evaluation,
        dataset=DatasetStats(
            users=data.n_users,
            items=data.n_items,
            interactions=len(data),
            train_interactions=int(split.train_mask.sum()),
            test_interactions=split.n_test,
        ),
        popularity={pid: int(c) for pid, c in zip(catalog.product_ids, counts, strict=True)},
    )


def iter_training_rows(db: Db) -> Iterator[tuple[str, str, str, float]]:
    cursor = db.events.find(
        TRAINING_EVENT_FILTER,
        {"_id": 0, "user_id": 1, "product_id": 1, "type": 1, "ts": 1},
        batch_size=5000,
    )
    for event in cursor:
        yield (
            str(event["user_id"]),
            str(event["product_id"]),
            str(event["type"]),
            as_utc(event["ts"]).timestamp(),
        )


# --- model persistence ---------------------------------------------------------------------


def save_model(db: Db, run_id: str, als: AlsModel, trained_at: datetime) -> None:
    payload = als.to_bytes()
    if len(payload) > 15 * 1024 * 1024:
        raise ValueError("model artifact exceeds MongoDB's 16 MB document limit")
    db.model_artifacts.insert_one(
        {
            "_id": run_id,
            "created_at": trained_at,
            "config": als.config.to_dict(),
            "items": als.n_items,
            "payload": Binary(payload),
        }
    )
    stale = list(db.model_artifacts.find({}, {"_id": 1}).sort("created_at", DESCENDING).skip(KEEP_ARTIFACTS))
    if stale:
        db.model_artifacts.delete_many({"_id": {"$in": [doc["_id"] for doc in stale]}})


def load_latest_model(db: Db) -> LoadedModel | None:
    doc = db.model_artifacts.find_one(sort=[("created_at", DESCENDING)])
    if doc is None:
        return None
    config = AlsConfig(**doc["config"])
    return LoadedModel(
        als=AlsModel.from_bytes(bytes(doc["payload"]), config),
        version=str(doc["_id"]),
        trained_at=as_utc(doc["created_at"]),
        config=config,
    )


# --- orchestration -------------------------------------------------------------------------


class TrainingCoordinator:
    """Runs at most one training job at a time (across processes, via a Mongo lock)."""

    def __init__(self, db: Db, engine: RecommenderEngine, *, cooldown_seconds: int, threads: int) -> None:
        self.db = db
        self.engine = engine
        self.cooldown_seconds = cooldown_seconds
        self.threads = threads

    def cooldown_remaining(self, trigger: Trigger = "admin") -> int:
        if trigger != "admin" or self.cooldown_seconds <= 0:
            return 0
        last = self.db.training_runs.find_one({"trigger": "admin"}, sort=[("started_at", DESCENDING)])
        if last is None:
            return 0
        elapsed = (utcnow() - as_utc(last["started_at"])).total_seconds()
        return max(0, int(np.ceil(self.cooldown_seconds - elapsed)))

    def _acquire_lock(self, run_id: str) -> bool:
        now = utcnow()
        try:
            self.db.meta.update_one(
                {
                    "_id": "training_lock",
                    "$or": [{"run_id": None}, {"acquired_at": {"$lt": now - STALE_LOCK_AFTER}}],
                },
                {"$set": {"run_id": run_id, "acquired_at": now}},
                upsert=True,
            )
        except DuplicateKeyError:
            return False
        lock = self.db.meta.find_one({"_id": "training_lock"})
        return lock is not None and lock.get("run_id") == run_id

    def _release_lock(self, run_id: str) -> None:
        self.db.meta.update_one({"_id": "training_lock", "run_id": run_id}, {"$set": {"run_id": None}})

    def start(self, trigger: Trigger, config: AlsConfig, *, background: bool = True) -> str:
        retry_after = self.cooldown_remaining(trigger)
        if retry_after > 0:
            raise CooldownActiveError(retry_after)
        run_id = str(ObjectId())
        if not self._acquire_lock(run_id):
            raise TrainingBusyError("a training run is already in progress")
        self.db.training_runs.insert_one(
            {
                "_id": run_id,
                "status": "running",
                "trigger": trigger,
                "started_at": utcnow(),
                "finished_at": None,
                "duration_seconds": None,
                "params": config.to_dict(),
                "dataset": None,
                "evaluation": None,
                "error": None,
            }
        )
        if background:
            threading.Thread(
                target=self.run, args=(run_id, config), name=f"train-{run_id}", daemon=True
            ).start()
        else:
            self.run(run_id, config)
        return run_id

    def run(self, run_id: str, config: AlsConfig) -> None:
        started = time.perf_counter()
        try:
            products = list(self.db.products.find({}, {"title": 1, "category": 1}))
            output = train_pipeline(products, iter_training_rows(self.db), config, threads=self.threads)
            trained_at = utcnow()
            save_model(self.db, run_id, output.als, trained_at)
            self.db.products.bulk_write(
                [
                    UpdateOne({"_id": pid}, {"$set": {"popularity": count}})
                    for pid, count in output.popularity.items()
                ]
            )
            self.engine.reload_catalog(self.db)
            self.engine.set_model(
                LoadedModel(als=output.als, version=run_id, trained_at=trained_at, config=config)
            )
            self.db.training_runs.update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "status": "succeeded",
                        "finished_at": trained_at,
                        "duration_seconds": round(time.perf_counter() - started, 2),
                        "dataset": asdict(output.dataset),
                        "evaluation": {
                            "k": output.evaluation.k,
                            "users_evaluated": output.evaluation.users_evaluated,
                            "holdout_fraction": HOLDOUT_FRACTION,
                            "models": {name: asdict(m) for name, m in output.evaluation.models.items()},
                        },
                    }
                },
            )
            log.info("training run %s succeeded in %.1fs", run_id, time.perf_counter() - started)
        except Exception as exc:
            log.exception("training run %s failed", run_id)
            self.db.training_runs.update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "status": "failed",
                        "finished_at": utcnow(),
                        "duration_seconds": round(time.perf_counter() - started, 2),
                        "error": str(exc)[:500],
                    }
                },
            )
        finally:
            self._release_lock(run_id)

    def recover_after_restart(self) -> None:
        """Fail runs a previous process left 'running' and free the lock.

        Assumes a single API instance (Render free tier): at startup nothing else can be
        training. With several instances, rely on STALE_LOCK_AFTER instead.
        """
        self.db.training_runs.update_many(
            {"status": "running"},
            {
                "$set": {
                    "status": "failed",
                    "finished_at": utcnow(),
                    "error": "interrupted by a server restart",
                }
            },
        )
        self.db.meta.update_one({"_id": "training_lock"}, {"$set": {"run_id": None}})
