from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status

from marketmind.deps import CurrentUser, DbDep
from marketmind.ratelimit import RateLimiter
from marketmind.schemas import EventAck, EventIn
from marketmind.timeutil import utcnow

router = APIRouter(tags=["events"])

# Refreshing a product page shouldn't count as fresh interest.
VIEW_DEDUP_WINDOW = timedelta(minutes=30)


@router.post("/events", response_model=EventAck, status_code=status.HTTP_202_ACCEPTED)
def track_event(body: EventIn, user: CurrentUser, db: DbDep, request: Request) -> EventAck:
    """Record client-side implicit feedback (views and recommendation clicks).

    Cart additions and purchases are recorded by the server when they happen, so a
    client can't fabricate them.
    """
    user_id = str(user["_id"])
    limiter: RateLimiter = request.app.state.rate_limiters["events"]
    if not limiter.allow(user_id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many events")
    if db.products.count_documents({"_id": body.product_id}, limit=1) == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    now = utcnow()
    if body.type == "view":
        recent = db.events.find_one(
            {
                "user_id": user_id,
                "product_id": body.product_id,
                "type": "view",
                "ts": {"$gte": now - VIEW_DEDUP_WINDOW},
            }
        )
        if recent is not None:
            return EventAck(accepted=True, deduplicated=True)

    event = {
        "user_id": user_id,
        "product_id": body.product_id,
        "type": body.type,
        "ts": now,
        "source": "live",
        "context": body.context,
    }
    if user.get("expires_at"):
        event["expires_at"] = user["expires_at"]
    db.events.insert_one(event)
    return EventAck(accepted=True)
