from __future__ import annotations

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError

from marketmind.demo import create_demo_user
from marketmind.deps import CurrentUser, DbDep, SettingsDep, rate_limited
from marketmind.ratelimit import RateLimiter
from marketmind.schemas import AuthOut, LoginIn, RegisterIn, User
from marketmind.security import hash_password, verify_password
from marketmind.services import issue_token, to_user
from marketmind.timeutil import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the email is unknown, so response time doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post(
    "/register",
    response_model=AuthOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limited("auth")],
)
def register(body: RegisterIn, db: DbDep, settings: SettingsDep) -> AuthOut:
    user = {
        "_id": ObjectId(),
        "email": body.email.lower(),
        "name": body.name,
        "password_hash": hash_password(body.password),
        "role": "customer",
        "is_demo": False,
        "created_at": utcnow(),
    }
    try:
        db.users.insert_one(user)
    except DuplicateKeyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from exc
    return issue_token(user, settings)


@router.post("/login", response_model=AuthOut, dependencies=[rate_limited("auth")])
def login(body: LoginIn, db: DbDep, settings: SettingsDep) -> AuthOut:
    user = db.users.find_one({"email": body.email.lower(), "is_demo": {"$ne": True}})
    password_hash = user.get("password_hash") if user else None
    valid = verify_password(body.password, password_hash or _DUMMY_HASH)
    if user is None or not password_hash or not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return issue_token(user, settings)


@router.post(
    "/demo",
    response_model=AuthOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limited("auth")],
)
def demo_login(db: DbDep, settings: SettingsDep, request: Request) -> AuthOut:
    """Create an isolated demo shopper with a real purchase history and sign them in."""
    limiter: RateLimiter = request.app.state.rate_limiters["demo_global"]
    if not limiter.allow("all"):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "The demo is very popular right now. Please try again in a few minutes.",
            headers={"Retry-After": "300"},
        )
    return issue_token(create_demo_user(db, settings), settings)


@router.get("/me", response_model=User)
def me(user: CurrentUser) -> User:
    return to_user(user)
