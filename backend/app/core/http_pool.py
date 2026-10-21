"""One pooled HTTP client per event loop for the calls made on every draft: Gemini, the local model, Presidio.

A client per call paid a new connection (and TLS handshake) every time. A pooled connection belongs to
the loop that opened it, so each loop gets its own client: a script or test that starts a new loop
never reuses a dead one. Callers pass timeout and auth per request, since the client is shared.
"""

import asyncio
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient] = weakref.WeakKeyDictionary()


def shared_client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None or client.is_closed:
        client = _clients[loop] = httpx.AsyncClient()
    return client


@asynccontextmanager
async def client_for(transport: httpx.AsyncBaseTransport | None) -> AsyncIterator[httpx.AsyncClient]:
    """The shared client, or one of its own over a test's transport, closed after the call as before."""
    if transport is None:
        yield shared_client()
        return
    async with httpx.AsyncClient(transport=transport) as client:
        yield client


async def close() -> None:
    client = _clients.pop(asyncio.get_running_loop(), None)
    if client is not None:
        await client.aclose()
