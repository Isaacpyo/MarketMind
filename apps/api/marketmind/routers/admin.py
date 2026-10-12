from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from pymongo import DESCENDING

from marketmind.deps import AdminUser, CoordinatorDep, DbDep, EngineDep
from marketmind.recsys.als import AlsConfig
from marketmind.schemas import AdminOverview, AlsParams, ModelInfo, TrainingRun
from marketmind.timeutil import as_utc, utcnow
from marketmind.training import CooldownActiveError, TrainingBusyError

router = APIRouter(prefix="/admin", tags=["admin"])


def to_run(doc: dict[str, Any]) -> TrainingRun:
    finished = doc.get("finished_at")
    return TrainingRun(
        id=str(doc["_id"]),
        status=doc["status"],
        trigger=doc["trigger"],
        started_at=as_utc(doc["started_at"]),
        finished_at=as_utc(finished) if finished else None,
        duration_seconds=doc.get("duration_seconds"),
        params=AlsParams(**doc["params"]),
        dataset=doc.get("dataset"),
        evaluation=doc.get("evaluation"),
        error=doc.get("error"),
    )


@router.get("/overview", response_model=AdminOverview)
def overview(_: AdminUser, db: DbDep, engine: EngineDep, coordinator: CoordinatorDep) -> AdminOverview:
    events_by_type = {
        str(row["_id"]): int(row["count"])
        for row in db.events.aggregate([{"$group": {"_id": "$type", "count": {"$sum": 1}}}])
    }
    model = engine.model
    live = {"source": "live"}
    since_model = (
        db.events.count_documents({**live, "ts": {"$gt": model.trained_at}})
        if model
        else db.events.count_documents(live)
    )
    latest = db.training_runs.find_one(sort=[("started_at", DESCENDING)])
    return AdminOverview(
        products=db.products.count_documents({}),
        registered_users=db.users.count_documents({"is_demo": {"$ne": True}}),
        demo_users=db.users.count_documents({"is_demo": True}),
        events_by_type=events_by_type,
        live_events_last_24h=db.events.count_documents(
            {**live, "ts": {"$gte": utcnow() - timedelta(hours=24)}}
        ),
        live_events_since_model=since_model,
        model=(
            ModelInfo(
                version=model.version,
                trained_at=model.trained_at,
                params=AlsParams(**model.config.to_dict()),
                items=model.als.n_items,
            )
            if model
            else None
        ),
        latest_run=to_run(latest) if latest else None,
        retrain_available_in_seconds=coordinator.cooldown_remaining(),
    )


@router.get("/runs", response_model=list[TrainingRun])
def list_runs(_: AdminUser, db: DbDep, limit: Annotated[int, Query(ge=1, le=50)] = 10) -> list[TrainingRun]:
    cursor = db.training_runs.find().sort("started_at", DESCENDING).limit(limit)
    return [to_run(doc) for doc in cursor]


@router.get("/runs/{run_id}", response_model=TrainingRun)
def get_run(_: AdminUser, db: DbDep, run_id: Annotated[str, Path(pattern=r"^[0-9a-f]{24}$")]) -> TrainingRun:
    doc = db.training_runs.find_one({"_id": run_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Training run not found")
    return to_run(doc)


@router.post("/retrain", response_model=TrainingRun, status_code=status.HTTP_202_ACCEPTED)
def retrain(
    _: AdminUser,
    db: DbDep,
    coordinator: CoordinatorDep,
    response: Response,
    params: AlsParams | None = None,
) -> TrainingRun:
    """Start a background training run (holdout evaluation + refit on all data)."""
    config = AlsConfig(**(params or AlsParams()).model_dump())
    try:
        run_id = coordinator.start("admin", config)
    except CooldownActiveError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"The model was retrained recently. Try again in {exc.retry_after}s.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except TrainingBusyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "A training run is already in progress") from exc
    response.headers["Location"] = f"/api/admin/runs/{run_id}"
    doc = db.training_runs.find_one({"_id": run_id})
    assert doc is not None  # noqa: S101 - inserted by coordinator.start
    return to_run(doc)
