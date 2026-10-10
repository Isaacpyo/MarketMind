from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current UTC time at millisecond precision, the resolution BSON stores.

    Truncating up front means a value echoed in a response equals the one read back later.
    """
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


def as_utc(value: datetime) -> datetime:
    """MongoDB stores UTC; drivers may hand back naive datetimes. Make them explicit."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
