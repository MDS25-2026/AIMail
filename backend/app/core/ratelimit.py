"""Rate limits (audit OWASP API8), shared by every API instance.

Size caps stop one huge request; this stops many small ones. Counters live in Postgres (fixed windows,
migration 0029), so several instances enforce one limit rather than one each. A signed-in caller is limited
as themselves; only unauthenticated routes fall back to the client address, read from the trusted proxy's
X-Forwarded-For when TRUSTED_PROXY_HOPS says one sits in front. Generation also has a budget across all
users, because the model quota is the project's, not each user's.

A fixed window lets a burst of up to twice the limit straddle a boundary; for abuse limits that is fine.
"""

import math
import time
from typing import Protocol

from fastapi import HTTPException, Request, status
from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.constants import (
    DETAIL_RATE_LIMIT,
    DETAIL_RATE_WINDOW_SECONDS,
    GENERATION_RATE_LIMIT,
    GENERATION_RATE_WINDOW_SECONDS,
    GLOBAL_GENERATION_RATE_LIMIT,
    INGEST_RATE_LIMIT,
    INGEST_RATE_WINDOW_SECONDS,
)
from app.db.models import RateLimitCounter
from app.db.session import get_sessionmaker

FORWARDED_FOR = "x-forwarded-for"
_ALL: list["RateLimiter"] = []
EVERYONE = "everyone"


class CounterStore(Protocol):
    async def hit(self, key: str, window_start: float) -> int: ...


class PostgresCounters:
    async def hit(self, key: str, window_start: float) -> int:
        statement = insert(RateLimitCounter).values(key=key, window_start=func.to_timestamp(window_start), hits=1)
        statement = statement.on_conflict_do_update(
            index_elements=["key", "window_start"], set_={"hits": RateLimitCounter.hits + 1},
        ).returning(literal_column("hits"))
        async with get_sessionmaker()() as session, session.begin():
            return await session.scalar(statement)


class MemoryCounters:
    """For a single process without a database (tests). Never selected in a deployed environment."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, float], int] = {}

    async def hit(self, key: str, window_start: float) -> int:
        self._hits[(key, window_start)] = self._hits.get((key, window_start), 0) + 1
        return self._hits[(key, window_start)]

    def reset(self) -> None:
        self._hits.clear()


def _client_address(request: Request) -> str:
    hops = get_settings().trusted_proxy_hops
    forwarded = [part.strip() for part in request.headers.get(FORWARDED_FOR, "").split(",") if part.strip()]
    if hops and len(forwarded) >= hops:
        return forwarded[-hops]  # the address the outermost trusted proxy saw
    return request.client.host if request.client else "unknown"


def caller_key(request: Request) -> str:
    principal = getattr(request.state, "principal", None)
    if principal is not None and principal.user_id is not None:
        return f"user:{principal.user_id}"
    if principal is not None and principal.is_service:
        return "service"
    return f"ip:{_client_address(request)}"


class RateLimiter:
    """A FastAPI dependency: at most `limit` requests per `window` seconds per caller."""

    def __init__(self, name: str, limit: int, window: int, *, global_limit: int | None = None) -> None:
        self.name = name
        self.limit = limit
        self.window = window
        self.global_limit = global_limit
        self.store: CounterStore = PostgresCounters()
        _ALL.append(self)

    def reset(self) -> None:
        if isinstance(self.store, MemoryCounters):
            self.store.reset()

    async def _over(self, key: str, limit: int, window_start: float) -> bool:
        return await self.store.hit(f"{self.name}:{key}", window_start) > limit

    async def __call__(self, request: Request) -> None:
        window_start = math.floor(time.time() / self.window) * self.window
        over = await self._over(caller_key(request), self.limit, window_start)
        if not over and self.global_limit is not None:
            over = await self._over(EVERYONE, self.global_limit, window_start)
        if over:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                f"rate limit: at most {self.limit} {self.name} requests per {self.window}s",
                                headers={"Retry-After": str(self.window)})


def all_limiters() -> list["RateLimiter"]:
    return list(_ALL)


rate_limit_ingest = RateLimiter("ingestion", INGEST_RATE_LIMIT, INGEST_RATE_WINDOW_SECONDS)
# Every route that spends model quota on request, per user and across everyone.
rate_limit_generation = RateLimiter("generation", GENERATION_RATE_LIMIT, GENERATION_RATE_WINDOW_SECONDS,
                                    global_limit=GLOBAL_GENERATION_RATE_LIMIT)
# Opening an email drafts it the first time, so the detail view spends quota too; its limit sits
# well above anyone reading their mail.
rate_limit_detail = RateLimiter("email detail", DETAIL_RATE_LIMIT, DETAIL_RATE_WINDOW_SECONDS)
