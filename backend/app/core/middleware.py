"""Request id, timing line and security headers on every response.

The request id is echoed in X-Request-ID and forwarded to the Lane C agent, so one id follows a
draft across both services' logs. Paths are logged without their query string: a query can carry
user text, and log lines must never hold email content.
"""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status

from app.core.health import HEALTH_PATHS
from app.core.logging_setup import request_id

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"
# An incoming id is kept only when it cannot smuggle anything into a log line.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# A JSON API renders nothing, so it may load nothing and be framed by no one. no-store keeps
# masked email out of browser and proxy caches.
API_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
# The demo page at / is the one HTML response; its script and styles are inline.
DEMO_PAGE_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'self'"
)
DEMO_PAGE_PATH = "/"


def printable(path: str) -> str:
    """The path with control characters escaped. ASGI has already percent-decoded it, so a %0A in
    the URL would otherwise start a forged log line; this runs before auth, for anyone."""
    return path.encode("unicode_escape").decode("ascii")


def incoming_request_id(value: str | None) -> str:
    return value if value and _SAFE_REQUEST_ID.match(value) else uuid.uuid4().hex


def apply_security_headers(response: Response, path: str) -> None:
    response.headers.update(API_HEADERS)
    if path == DEMO_PAGE_PATH:
        response.headers["Content-Security-Policy"] = DEMO_PAGE_CSP


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    token = request_id.set(incoming_request_id(request.headers.get(REQUEST_ID_HEADER)))
    started = time.perf_counter()
    try:
        response = await call_next(request)
        apply_security_headers(response, request.url.path)
        response.headers[REQUEST_ID_HEADER] = request_id.get()
        # A host probes every few seconds; only a failing probe is worth a line at INFO.
        is_quiet = request.url.path in HEALTH_PATHS and response.status_code < status.HTTP_400_BAD_REQUEST
        logger.log(logging.DEBUG if is_quiet else logging.INFO, "%s %s -> %d in %.0f ms", request.method,
                   printable(request.url.path), response.status_code, (time.perf_counter() - started) * 1000)
        return response
    finally:
        request_id.reset(token)
