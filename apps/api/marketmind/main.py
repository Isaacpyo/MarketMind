"""FastAPI application factory."""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from marketmind.config import Settings, get_settings
from marketmind.db import Db, connect, ensure_indexes
from marketmind.engine import RecommenderEngine
from marketmind.ratelimit import RateLimiter
from marketmind.recsys.als import AlsConfig
from marketmind.routers import admin, auth, cart, events, health, orders, products, recommendations
from marketmind.seed import seed_database
from marketmind.training import TrainingBusyError, TrainingCoordinator, load_latest_model

log = logging.getLogger("marketmind")


def prepare(db: Db, settings: Settings, engine: RecommenderEngine, coordinator: TrainingCoordinator) -> None:
    """Make the app useful: indexes, seed data, catalogue, model (training one if needed)."""
    ensure_indexes(db)
    coordinator.recover_after_restart()
    if settings.auto_seed:
        seed_database(db, settings.seed_dir)
    engine.reload_catalog(db)
    model = load_latest_model(db)
    engine.set_model(model)
    if model is None and settings.train_on_startup and engine.ready:
        try:
            coordinator.start("startup", AlsConfig(), background=False)
        except TrainingBusyError:
            log.info("another process is already training")


PREPARE_MAX_BACKOFF_SECONDS = 60.0


def _prepare_in_background(app: FastAPI, stop: threading.Event) -> None:
    """Retry with backoff: a cold Atlas cluster or a network blip must not leave the API unready."""
    delay = 2.0
    while not stop.is_set():
        try:
            prepare(app.state.db, app.state.settings, app.state.engine, app.state.coordinator)
            log.info("startup preparation finished")
            return
        except Exception:
            log.exception("startup preparation failed; retrying in %.0fs", delay)
            stop.wait(delay)
            delay = min(delay * 2, PREPARE_MAX_BACKOFF_SECONDS)


def create_app(settings: Settings | None = None, db: Db | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = None
        database = db
        if database is None:
            client, database = connect(settings.mongodb_uri, settings.mongodb_db)
        engine = RecommenderEngine()
        app.state.settings = settings
        app.state.db = database
        app.state.engine = engine
        app.state.coordinator = TrainingCoordinator(
            database,
            engine,
            cooldown_seconds=settings.retrain_cooldown_seconds,
            threads=settings.train_threads,
        )
        app.state.rate_limiters = {
            "auth": RateLimiter(settings.auth_rate_limit_per_minute),
            "events": RateLimiter(settings.events_rate_limit_per_minute),
            "demo_global": RateLimiter(settings.demo_global_limit_per_hour, window_seconds=3600),
        }
        stop = threading.Event()
        if settings.app_env == "test":
            prepare(database, settings, engine, app.state.coordinator)
        else:
            # Bind the port immediately so a waking free-tier instance answers /health while
            # seeding and model loading continue in the background.
            threading.Thread(target=_prepare_in_background, args=(app, stop), daemon=True).start()
        yield
        stop.set()
        if client is not None:
            client.close()

    app = FastAPI(
        title="MarketMind API",
        version="0.1.0",
        summary="E-commerce storefront with ALS + TF-IDF hybrid recommendations",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    for module in (health, auth, products, recommendations, events, cart, orders, admin):
        app.include_router(module.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": "MarketMind API", "docs": "/docs", "health": "/api/health"}

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def app_factory() -> FastAPI:
    """Entry point for `uvicorn --factory marketmind.main:app_factory`."""
    return create_app()
