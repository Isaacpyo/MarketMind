from __future__ import annotations

from fastapi import APIRouter

from marketmind.deps import DbDep, EngineDep
from marketmind.schemas import Health
from marketmind.seed import is_seeded

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health(db: DbDep, engine: EngineDep) -> Health:
    """Cheap liveness probe; the web app polls it to detect a sleeping free-tier server."""
    model = engine.model
    return Health(
        status="ok",
        ready=engine.ready,
        seeded=is_seeded(db),
        model_version=model.version if model else None,
    )
