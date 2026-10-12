from __future__ import annotations

from fastapi import APIRouter
from pymongo.errors import PyMongoError

from marketmind.deps import DbDep, EngineDep
from marketmind.schemas import Health
from marketmind.seed import is_seeded

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health(db: DbDep, engine: EngineDep) -> Health:
    """Cheap liveness probe; the web app polls it to detect a sleeping free-tier server.

    It never fails because of MongoDB: a database blip shouldn't make Render restart a healthy
    process. Readiness is reported separately in the body.
    """
    model = engine.model
    try:
        seeded = is_seeded(db)
    except PyMongoError:
        seeded = False
    return Health(
        status="ok",
        ready=engine.ready,
        seeded=seeded,
        model_version=model.version if model else None,
    )
