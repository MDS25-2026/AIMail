"""Per-client sliding-window rate limits (audit OWASP API8).

Size caps stop one huge request; this stops many small ones. Deliberately hand-rolled rather
than adding slowapi: it is a sliding window over a deque of timestamps, and a new dependency
for that is not worth the supply-chain surface.

Known limits, acceptable for a single-host deployment and fixed by moving the counter to Redis
if this ever runs multi-worker: state is per process, so N uvicorn workers allow N times the
quota; and the client is the socket IP, so a reverse proxy needs X-Forwarded-For handling
before this means anything in production. Idle clients are evicted, so memory stays bounded.
"""

import time
from collections import deque

from fastapi import HTTPException, Request, status

from app.core.constants import (
    GENERATION_RATE_LIMIT,
    GENERATION_RATE_WINDOW_SECONDS,
    INGEST_RATE_LIMIT,
    INGEST_RATE_WINDOW_SECONDS,
)


class RateLimiter:
    """A FastAPI dependency: at most `limit` requests per `window` seconds per client."""

    def __init__(self, name: str, limit: int, window: int) -> None:
        self.name = name
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def _evict_idle(self, cutoff: float) -> None:
        idle = [client for client, hits in self._hits.items() if not hits or hits[-1] < cutoff]
        for client in idle:
            del self._hits[client]

    async def __call__(self, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window
        self._evict_idle(cutoff)
        hits = self._hits.setdefault(client, deque())
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"rate limit: at most {self.limit} {self.name} requests per {self.window}s",
                headers={"Retry-After": str(self.window)},
            )
        hits.append(now)


rate_limit_ingest = RateLimiter("ingestion", INGEST_RATE_LIMIT, INGEST_RATE_WINDOW_SECONDS)
# Every route that spends Gemini quota on request, so a stuck client cannot drain the free tier.
rate_limit_generation = RateLimiter(
    "generation", GENERATION_RATE_LIMIT, GENERATION_RATE_WINDOW_SECONDS
)
