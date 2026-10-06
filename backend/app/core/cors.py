"""CORS scoped by path and origin: credentialed only for the dashboard's exact origins, credential-free
for everything else.

Browsers treat every localhost port as the same site, so a SameSite=Strict cookie still travels
from a page on another local port. The admin console's protection therefore rests on CORS: only
the listed dashboard origins may read admin responses or pass the preflight that its
X-AIMail-Admin header forces. The same origins may send the dashboard session cookie with the
X-AIMail-Client header to the rest of the API (ADR 0005). Every other origin keeps the any-local-port
policy, but without credentials, so it never carries either cookie anywhere.
"""

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.admin.auth import CSRF_HEADER
from app.core.auth import CLIENT_HEADER

ADMIN_METHODS = ["GET", "POST", "DELETE"]
ADMIN_HEADERS = ["Content-Type", CSRF_HEADER]
DASHBOARD_METHODS = ["GET", "POST", "DELETE"]
DASHBOARD_HEADERS = ["Content-Type", CLIENT_HEADER]


def origins_from(raw: str) -> list[str]:
    """A comma-separated origin list; blanks dropped, and never a wildcard."""
    return [origin.strip() for origin in raw.split(",") if origin.strip() and origin.strip() != "*"]


class PathScopedCORS:
    def __init__(self, app: ASGIApp, admin_prefix: str, admin_origins: list[str],
                 public_origins: list[str], public_origin_regex: str) -> None:
        self.admin_prefix = admin_prefix
        self.admin = CORSMiddleware(app, allow_origins=admin_origins, allow_credentials=True,
                                    allow_methods=ADMIN_METHODS, allow_headers=ADMIN_HEADERS)
        self.dashboard_origins = frozenset(admin_origins)
        self.dashboard = CORSMiddleware(app, allow_origins=admin_origins, allow_credentials=True,
                                        allow_methods=DASHBOARD_METHODS,
                                        allow_headers=DASHBOARD_HEADERS)
        self.public = CORSMiddleware(app, allow_origins=public_origins,
                                     allow_origin_regex=public_origin_regex,
                                     allow_methods=["*"], allow_headers=["*"])

    def _is_admin(self, scope: Scope) -> bool:
        path = scope.get("path", "")
        return path == self.admin_prefix or path.startswith(self.admin_prefix + "/")

    def _origin(self, scope: Scope) -> str:
        for name, value in scope.get("headers", []):
            if name == b"origin":
                return value.decode("latin-1")
        return ""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.public(scope, receive, send)
            return
        if self._is_admin(scope):
            target = self.admin
        elif self._origin(scope) in self.dashboard_origins:
            target = self.dashboard
        else:
            target = self.public
        await target(scope, receive, send)
