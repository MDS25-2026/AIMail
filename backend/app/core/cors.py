"""CORS scoped by path: credentialed for the admin console's exact origins, credential-free for
everything else.

Browsers treat every localhost port as the same site, so a SameSite=Strict cookie still travels
from a page on another local port. The admin console's protection therefore rests on CORS: only
the listed dashboard origins may read admin responses or pass the preflight that its
X-AIMail-Admin header forces. The rest of the API keeps its any-local-port policy, but without
credentials, so it never carries the admin cookie anywhere.
"""

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.admin.auth import CSRF_HEADER

ADMIN_METHODS = ["GET", "POST", "DELETE"]
ADMIN_HEADERS = ["Content-Type", CSRF_HEADER]


def origins_from(raw: str) -> list[str]:
    """A comma-separated origin list; blanks dropped, and never a wildcard."""
    return [origin.strip() for origin in raw.split(",") if origin.strip() and origin.strip() != "*"]


class PathScopedCORS:
    def __init__(self, app: ASGIApp, admin_prefix: str, admin_origins: list[str],
                 public_origins: list[str], public_origin_regex: str) -> None:
        self.admin_prefix = admin_prefix
        self.admin = CORSMiddleware(app, allow_origins=admin_origins, allow_credentials=True,
                                    allow_methods=ADMIN_METHODS, allow_headers=ADMIN_HEADERS)
        self.public = CORSMiddleware(app, allow_origins=public_origins,
                                     allow_origin_regex=public_origin_regex,
                                     allow_methods=["*"], allow_headers=["*"])

    def _is_admin(self, scope: Scope) -> bool:
        path = scope.get("path", "")
        return path == self.admin_prefix or path.startswith(self.admin_prefix + "/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        target = self.admin if scope["type"] == "http" and self._is_admin(scope) else self.public
        await target(scope, receive, send)
