"""Per-IP rate limit for the ingestion routes (audit OWASP API8).

Size caps stop one huge upload; this stops many small ones. Deliberately hand-rolled rather
than adding slowapi: it is a sliding window over a deque of timestamps, and a new dependency
for that is not worth the supply-chain surface.

Known limits, all acceptable for a single-host deployment and all fixed by moving the counter
to Redis if this ever runs multi-worker: state is per process, so N uvicorn workers allow N
times the quota; the client IP is taken from the socket, so a reverse proxy would need
X-Forwarded-For handling before this means anything in production; and the map holds one entry
per IP seen since start, which is fine for a known client set and would need eviction if this
were ever public.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.constants import INGEST_RATE_LIMIT, INGEST_RATE_WINDOW_SECONDS

_hits: dict[str, deque[float]] = defaultdict(deque)


async def rate_limit_ingest(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _hits[client]

    cutoff = now - INGEST_RATE_WINDOW_SECONDS
    while window and window[0] < cutoff:
        window.popleft()

    if len(window) >= INGEST_RATE_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"rate limit: at most {INGEST_RATE_LIMIT} ingestion requests per"
            f" {INGEST_RATE_WINDOW_SECONDS}s",
            headers={"Retry-After": str(INGEST_RATE_WINDOW_SECONDS)},
        )

    window.append(now)
