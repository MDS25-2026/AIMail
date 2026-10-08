"""Admin console auth (ADR 0004) with real ES256 tokens from a locally generated key."""

import time
from dataclasses import dataclass

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.admin import app as admin_routes
from app.admin import auth, stats
from app.admin.schemas import MailboxCounts, ModelHealth, Overview, PrivacyCounts
from app.core import supabase_auth
from app.core.config import get_settings
from app.db.models import AuditLog
from app.main import app
from tests.conftest import AUTH_HEADERS

SUPABASE = "https://project.supabase.co"
ISSUER = f"{SUPABASE}/auth/v1"
KEY = ec.generate_private_key(ec.SECP256R1())
FOREIGN_KEY = ec.generate_private_key(ec.SECP256R1())
CSRF = {auth.CSRF_HEADER: "1"}


@dataclass
class _SigningKey:
    key: object


class _FakeJwks:
    def get_signing_key_from_jwt(self, token: str) -> _SigningKey:
        return _SigningKey(KEY.public_key())


def mint(role: str | None = "admin", *, key=KEY, aud: str = "authenticated", iss: str = ISSUER,
         expires_in: int = 3600, user_metadata: dict | None = None) -> str:
    claims = {"sub": "user-1", "email": "ops@example.com", "aud": aud, "iss": iss,
              "exp": int(time.time()) + expires_in,
              "app_metadata": {"role": role} if role else {},
              "user_metadata": user_metadata or {}}
    return jwt.encode(claims, key, algorithm="ES256")


def cookie(token: str) -> dict:
    return {"Cookie": f"{auth.ACCESS_COOKIE}={token}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", SUPABASE)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "publishable-test-key")
    monkeypatch.setenv("BACKEND_API_TOKEN", "test-token-not-a-real-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused:unused@127.0.0.1:5432/unused")
    monkeypatch.setenv("GOOGLE_API_KEY", "unused")
    get_settings.cache_clear()
    monkeypatch.setattr(supabase_auth, "_jwks", lambda base: _FakeJwks())

    async def fake_overview(session, days):
        return Overview(days=days, mailbox=MailboxCounts(total=1, masking_pending=0, masking_abandoned=0, generated=1,
                        awaiting_review=0, sent=0, unread=1),
                        privacy=PrivacyCounts(quarantined=0, released=0, degraded_before_fix=0,
                        attachment_text_dropped=0, pages_withheld=0, attachment_failures=0),
                        review_reasons=[], models=ModelHealth(drafts=0, attempts=0, outcomes=[],
                        drafts_using_fallback=0, model_ms_p50=None, model_ms_p95=None))

    monkeypatch.setattr(stats, "overview", fake_overview)
    admin_routes.rate_limit_sign_in.reset()

    async def no_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(admin_routes, "audit", no_audit)
    yield TestClient(app)
    get_settings.cache_clear()


def supabase(monkeypatch, handler) -> list[str]:
    seen: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path + ("?" + request.url.query.decode() if request.url.query else ""))
        return handler(request)

    monkeypatch.setattr(supabase_auth, "transport", httpx.MockTransport(respond))
    return seen


def session_reply(token: str) -> httpx.Response:
    return httpx.Response(200, json={"access_token": token, "refresh_token": "r1", "expires_in": 3600})


# ---------- Who gets in ----------

def test_no_session_is_signed_out(client):
    response = client.get("/admin/overview")
    assert response.status_code == 401 and response.json()["error"]["code"] == "admin_signed_out"


def test_the_shared_dashboard_token_does_not_open_admin(client):
    assert client.get("/admin/overview", headers=AUTH_HEADERS).status_code == 401


def test_an_admin_session_reads_the_console(client):
    response = client.get("/admin/overview", headers=cookie(mint()))
    assert response.status_code == 200 and response.json()["mailbox"]["total"] == 1


def test_a_real_account_without_the_role_is_forbidden(client):
    response = client.get("/admin/overview", headers=cookie(mint(role=None)))
    assert response.status_code == 403 and response.json()["error"]["code"] == "not_an_admin"


def test_a_role_claimed_in_user_metadata_is_ignored(client):
    """user_metadata is editable by the user; only app_metadata grants admin."""
    spoofed = mint(role=None, user_metadata={"role": "admin"})
    assert client.get("/admin/overview", headers=cookie(spoofed)).status_code == 403


@pytest.mark.parametrize("token", [
    mint(expires_in=-60),
    mint(aud="anon"),
    mint(iss="https://evil.example/auth/v1"),
    mint(key=FOREIGN_KEY),
    "not-a-jwt",
])
def test_an_expired_foreign_or_malformed_token_is_rejected(client, token):
    response = client.get("/admin/overview", headers=cookie(token))
    assert response.status_code == 401 and response.json()["error"]["code"] == "admin_session_invalid"


# ---------- Sign-in ----------

def test_sign_in_sets_httponly_strict_cookies_and_never_returns_the_token(client, monkeypatch):
    token = mint()
    supabase(monkeypatch, lambda request: session_reply(token))
    response = client.post("/admin/session", json={"email": "ops@example.com", "password": "x"},
                           headers=CSRF)
    assert response.status_code == 200 and response.json() == {"email": "ops@example.com"}
    assert token not in response.text
    cookies = response.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith(auth.ACCESS_COOKIE + "="))
    assert "HttpOnly" in access and "SameSite=strict" in access and "Path=/admin" in access
    assert any(c.startswith(auth.REFRESH_COOKIE + "=") and "Path=/admin/session" in c for c in cookies)


def test_a_non_admin_sign_in_is_refused_and_its_session_ended(client, monkeypatch):
    seen = supabase(monkeypatch, lambda request: session_reply(mint(role=None))
                    if "token" in request.url.path else httpx.Response(204))
    response = client.post("/admin/session", json={"email": "a@b.c", "password": "x"}, headers=CSRF)
    # Told the same as a wrong password, so the form cannot confirm a valid one.
    assert response.status_code == 401 and response.json()["error"]["code"] == "invalid_credentials"
    assert "set-cookie" not in response.headers
    assert any(path.endswith("/logout") for path in seen)


def test_wrong_credentials_are_a_plain_401(client, monkeypatch):
    supabase(monkeypatch, lambda request: httpx.Response(400, json={"error": "invalid_grant"}))
    response = client.post("/admin/session", json={"email": "a@b.c", "password": "bad"}, headers=CSRF)
    assert response.status_code == 401 and response.json()["error"]["code"] == "invalid_credentials"


def test_sign_in_without_the_admin_header_is_refused(client):
    response = client.post("/admin/session", json={"email": "a@b.c", "password": "x"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "admin_header_missing"


def test_password_guessing_is_rate_limited(client, monkeypatch):
    supabase(monkeypatch, lambda request: httpx.Response(400))
    for _ in range(5):
        client.post("/admin/session", json={"email": "a@b.c", "password": "x"}, headers=CSRF)
    response = client.post("/admin/session", json={"email": "a@b.c", "password": "x"}, headers=CSRF)
    assert response.status_code == 429


def test_unconfigured_admin_auth_fails_closed(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_ANON_KEY", "")
    get_settings.cache_clear()
    response = client.post("/admin/session", json={"email": "a@b.c", "password": "x"}, headers=CSRF)
    assert response.status_code == 503 and response.json()["error"]["code"] == "admin_auth_not_configured"


def test_sign_out_clears_both_cookies(client, monkeypatch):
    supabase(monkeypatch, lambda request: httpx.Response(204))
    response = client.delete("/admin/session", headers={**CSRF, **cookie(mint())})
    assert response.status_code == 204
    cleared = response.headers.get_list("set-cookie")
    assert len(cleared) == 2
    assert all("Max-Age=0" in c for c in cleared)


# ---------- What the console shows ----------

@pytest.mark.parametrize("reason, category", [
    ("does not address: Send the invoice to Aisyah", "does not address"),
    ("figures not in source: 1250, 30", "figures not in source"),
    ("needed 2 refine round(s)", "needed # refine round(s)"),
    ("confidence 0.85 below 0.9", "confidence # below #"),
])
def test_review_reasons_are_categories_never_quoted_text(reason, category):
    assert stats.reason_category(reason) == category


def test_privacy_counts_read_the_audit_trail():
    rows = [
        AuditLog(action="quarantine_message", success=True, detail="msg a: NER unavailable"),
        AuditLog(action="remask_message", success=True, detail="msg a released"),
        AuditLog(action="read_attachment", success=True,
                 detail="msg b: application/pdf, 3 page(s), 1 redacted image(s) sent for OCR, 2 withheld locally, 90 chars"),
        AuditLog(action="drop_attachment_text", success=False, detail="msg c: dropped"),
        AuditLog(action="read_attachment", success=True, detail="msg f: image/png, 1 page(s); withheld=3"),
        AuditLog(action="ocr_attachment", success=False, detail="msg d: read locally failed"),
        AuditLog(action="store_message", success=True, detail="msg e stored (presidio degraded: regex-only)"),
    ]
    counts = stats.privacy_counts(rows)
    assert (counts.quarantined, counts.released, counts.pages_withheld) == (1, 1, 5)
    assert (counts.attachment_text_dropped, counts.attachment_failures, counts.degraded_before_fix) == (1, 1, 1)


def test_model_health_counts_retries_fallbacks_and_latency():
    checks = [
        {"model_calls": [{"model": "a", "outcome": "http_503", "ms": 100},
                         {"model": "b", "outcome": "ok", "ms": 300}]},
        {"model_calls": [{"model": "a", "outcome": "ok", "ms": 200}]},
        {"review_reasons": []},
    ]
    health = stats.model_health(checks)
    assert (health.drafts, health.attempts, health.drafts_using_fallback) == (2, 3, 1)
    assert (health.model_ms_p50, health.model_ms_p95) == (200, 400)


# ---------- CORS: the admin session travels only to the dashboard's own origins ----------

def _preflight(client, path: str, origin: str):
    return client.options(path, headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": f"content-type,{auth.CSRF_HEADER.lower()}"})


def test_the_dashboard_origin_may_carry_the_admin_session(client):
    response = _preflight(client, "/admin/session", "http://localhost:8090")
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8090"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize("origin", ["http://localhost:8080", "http://127.0.0.1:5173",
                                    "https://evil.example"])
def test_any_other_origin_cannot_pass_the_admin_preflight(client, origin):
    """Every localhost port is the same site, so SameSite cookies still flow; CORS is the wall."""
    response = _preflight(client, "/admin/session", origin)
    assert response.headers.get("access-control-allow-origin") is None


def test_the_rest_of_the_api_never_allows_credentials(client):
    response = client.get("/", headers={"Origin": "http://localhost:8080"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8080"
    assert response.headers.get("access-control-allow-credentials") is None


def test_signing_out_after_the_access_cookie_expired_still_revokes(client, monkeypatch):
    fresh = mint()
    seen = supabase(monkeypatch, lambda request: session_reply(fresh)
                    if "refresh_token" in (request.url.query.decode()) else httpx.Response(204))
    response = client.delete("/admin/session",
                             headers={**CSRF, "Cookie": f"{auth.REFRESH_COOKIE}=r1"})
    assert response.status_code == 204
    assert any(path.endswith("/logout") for path in seen)


def test_a_forged_key_id_triggers_at_most_one_refetch(monkeypatch):
    fetches = []

    class _Client:
        def get_signing_keys(self):
            fetches.append(1)
            return []

    key_set = supabase_auth._KeySet.__new__(supabase_auth._KeySet)
    key_set._client, key_set._keys, key_set._fetched_at = _Client(), {}, float("-inf")
    forged = jwt.encode({"sub": "x"}, KEY, algorithm="ES256", headers={"kid": "forged"})
    for _ in range(5):
        with pytest.raises(jwt.InvalidTokenError):
            key_set.get_signing_key_from_jwt(forged)
    assert len(fetches) == 1


def test_thread_context_is_prose_not_markup():
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.dashboard import thread_context
    from app.db.models import Message

    html = "<html><head><style>p{color:red}</style></head><body><p>Please send the Q3 figures.</p></body></html>"
    earlier = Message(id=uuid4(), received_at=datetime(2026, 9, 1, 9, tzinfo=timezone.utc), body_masked=html)
    current = Message(id=uuid4(), received_at=datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
    assert thread_context(current, [earlier]) == "Earlier message 1:\nPlease send the Q3 figures."
