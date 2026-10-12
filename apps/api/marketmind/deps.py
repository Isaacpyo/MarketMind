"""FastAPI dependencies: database, engine, auth and rate limiting."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from marketmind.config import Settings
from marketmind.db import Db
from marketmind.engine import EngineNotReadyError, RecommenderEngine
from marketmind.ratelimit import RateLimiter
from marketmind.recsys.hybrid import HybridRecommender
from marketmind.security import decode_access_token
from marketmind.training import TrainingCoordinator


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Db:
    db: Db = request.app.state.db
    return db


def get_engine(request: Request) -> RecommenderEngine:
    engine: RecommenderEngine = request.app.state.engine
    return engine


def get_recommender(engine: Annotated[RecommenderEngine, Depends(get_engine)]) -> HybridRecommender:
    try:
        return engine.recommender
    except EngineNotReadyError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Catalogue is still loading, try again shortly"
        ) from exc


def get_coordinator(request: Request) -> TrainingCoordinator:
    coordinator: TrainingCoordinator = request.app.state.coordinator
    return coordinator


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Db, Depends(get_db)]
EngineDep = Annotated[RecommenderEngine, Depends(get_engine)]
RecommenderDep = Annotated[HybridRecommender, Depends(get_recommender)]
CoordinatorDep = Annotated[TrainingCoordinator, Depends(get_coordinator)]

_bearer = HTTPBearer(auto_error=False)

UserDoc = dict[str, Any]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    db: DbDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserDoc:
    if credentials is None:
        raise _unauthorized("Sign in to continue")
    try:
        claims = decode_access_token(credentials.credentials, settings.jwt_secret.get_secret_value())
        user_id = ObjectId(str(claims["sub"]))
    except (jwt.InvalidTokenError, InvalidId, KeyError) as exc:
        raise _unauthorized("Your session has expired, please sign in again") from exc
    user = db.users.find_one({"_id": user_id})
    if user is None:
        raise _unauthorized("Your session has expired, please sign in again")
    return user


CurrentUser = Annotated[UserDoc, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> UserDoc:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


AdminUser = Annotated[UserDoc, Depends(require_admin)]


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        # The right-most entry was appended by our proxy; anything left of it is client-supplied.
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def rate_limited(bucket: str, key: Callable[[Request, Settings], str] = client_ip) -> Any:
    """Dependency factory: 429 when the caller exceeds the bucket's per-minute limit."""

    def dependency(request: Request, settings: SettingsDep) -> None:
        limiters: dict[str, RateLimiter] = request.app.state.rate_limiters
        if not limiters[bucket].allow(key(request, settings)):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests, slow down a little",
                headers={"Retry-After": "60"},
            )

    return Depends(dependency)
