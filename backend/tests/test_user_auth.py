"""Dashboard sign-in (ADR 0005): who may call the API, and whose mail they may see.

The browser used to carry the shared API token. Now a person signs in with Google through
Supabase; the session lives in HttpOnly cookies, scripts keep the shared token, and a signed-in
user sees only the mailbox they own.
"""

import base64
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core import supabase_auth
from app.core.auth import CLIENT_HEADER, SESSION_COOKIE
from app.core.config import get_settings
from app.dashboard import _to_email
from app.db.models import Message
from app.main import app
from tests.conftest import API_TOKEN

SUPABASE = "https://project.supabase.co"
AUTH_BASE = f"{SUPABASE}/auth/v1"
OWNER = "owner@gmail.com"
EMAIL = _to_email(Message(id=uuid4(), subject="Hi", created_at=datetime(2026, 10, 4, tzinfo=timezone.utc)))
KEY = ec.generate_private_key(ec.SECP256R1())


@dataclass(frozen=True)
class _SigningKey:
    key: object


class _FakeJwks:
    def get_signing_key_from_jwt(self, token):
        return _SigningKey(KEY.public_key())


def _token(email: str) -> str:
    claims = {"sub": f"user-{email}", "email": email, "aud": "authenticated", "iss": AUTH_BASE,
              "exp": int(time.time()) + 600}
    return jwt.encode(claims, KEY, algorithm="ES256")


@pytest.fixture
def client(monkeypatch, test_settings):
    for name, value in (("SUPABASE_URL", SUPABASE), ("SUPABASE_ANON_KEY", "anon"),
                        ("MAILBOX_OWNER_EMAIL", OWNER), ("BACKEND_PUBLIC_URL", "http://localhost:8000"),
                        ("DASHBOARD_URL", "http://localhost:8090"), ("ADMIN_COOKIE_SECURE", "false")):
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    monkeypatch.setattr(supabase_auth, "_jwks", lambda base: _FakeJwks())

    async def emails():
        return [EMAIL]

    async def detail(message_id):
        return EMAIL

    monkeypatch.setattr("app.main.list_dashboard_emails", emails)
    monkeypatch.setattr("app.main.email_detail", detail)
    return TestClient(app)


def _signed_in(client: TestClient, email: str) -> TestClient:
    client.cookies.set(SESSION_COOKIE, _token(email))
    return client


# ---------- Who may call ----------

def test_no_cookie_and_no_bearer_is_401(client):
    assert client.get("/emails").status_code == 401


def test_the_shared_token_still_works_for_scripts(client):
    response = client.get("/emails", headers={"Authorization": f"Bearer {API_TOKEN}"})
    assert response.status_code == 200 and response.json() == [EMAIL.model_dump(mode="json")]


def test_a_session_cookie_works_for_reads(client):
    assert _signed_in(client, OWNER).get("/emails").json() == [EMAIL.model_dump(mode="json")]


def test_a_cookie_request_that_changes_state_needs_the_client_header(client):
    response = _signed_in(client, OWNER).post("/emails/e1/send", json={"draft": "Thanks."})
    assert response.status_code == 403 and response.json()["detail"] == "client_header_missing"


def test_a_supabase_bearer_works_without_the_header(client):
    response = client.get("/emails", headers={"Authorization": f"Bearer {_token(OWNER)}"})
    assert response.status_code == 200


def test_a_forged_session_is_401(client):
    foreign = ec.generate_private_key(ec.SECP256R1())
    forged = jwt.encode({"sub": "x", "email": OWNER, "aud": "authenticated", "iss": AUTH_BASE,
                         "exp": int(time.time()) + 600}, foreign, algorithm="ES256")
    client.cookies.set(SESSION_COOKIE, forged)
    assert client.get("/emails").status_code == 401


# ---------- Whose mail ----------

def test_another_user_sees_an_empty_inbox(client):
    assert _signed_in(client, "someone.else@gmail.com").get("/emails").json() == []


def test_another_user_gets_404_for_an_email_id(client):
    assert _signed_in(client, "someone.else@gmail.com").get("/emails/e1").status_code == 404


def test_the_owner_match_ignores_case(client):
    assert _signed_in(client, "Owner@Gmail.com").get("/emails").json() == [EMAIL.model_dump(mode="json")]


def test_the_session_endpoint_says_whether_a_mailbox_is_connected(client):
    assert _signed_in(client, OWNER).get("/auth/session").json() == {"email": OWNER, "hasMailbox": True}
    other = _signed_in(client, "x@gmail.com").get("/auth/session").json()
    assert other["hasMailbox"] is False


# ---------- Signing in with Google ----------

def test_starting_sign_in_redirects_to_supabase_with_a_pkce_challenge(client):
    response = client.get("/auth/google/start", follow_redirects=False)
    target = urlparse(response.headers["location"])
    query = parse_qs(target.query)
    assert f"{target.scheme}://{target.netloc}{target.path}" == f"{AUTH_BASE}/authorize"
    assert query["provider"] == ["google"] and query["code_challenge_method"] == ["s256"]
    assert query["redirect_to"] == ["http://localhost:8000/auth/callback"]
    verifier = response.cookies.get("aimail_pkce")
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert query["code_challenge"] == [expected.decode()]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_the_callback_exchanges_the_code_and_sets_the_session(client, monkeypatch):
    seen = {}

    def supabase(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["body"] = str(request.url), request.read()
        return httpx.Response(200, json={"access_token": _token(OWNER), "refresh_token": "r1",
                                         "expires_in": 3600})

    monkeypatch.setattr(supabase_auth, "transport", httpx.MockTransport(supabase))
    client.cookies.set("aimail_pkce", "the-verifier")
    response = client.get("/auth/callback?code=abc", follow_redirects=False)
    assert seen["url"].endswith("/token?grant_type=pkce")
    assert b'"code_verifier":"the-verifier"' in seen["body"].replace(b" ", b"")
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "http://localhost:8090"
    cookies = " ".join(response.headers.get_list("set-cookie")).lower()
    assert f"{SESSION_COOKIE}=" in cookies and "samesite=strict" in cookies


def test_a_callback_without_the_verifier_goes_back_to_sign_in_with_an_error(client):
    response = client.get("/auth/callback?code=abc", follow_redirects=False)
    assert response.headers["location"] == "http://localhost:8090/signin?error=sign_in_failed"


def test_signing_out_needs_the_header_and_clears_the_cookies(client, monkeypatch):
    monkeypatch.setattr(supabase_auth, "transport",
                        httpx.MockTransport(lambda request: httpx.Response(204)))
    signed_in = _signed_in(client, OWNER)
    assert signed_in.delete("/auth/session").status_code == 403
    response = signed_in.delete("/auth/session", headers={CLIENT_HEADER: "1"})
    assert response.status_code == 204
    assert f"{SESSION_COOKIE}=" in " ".join(response.headers.get_list("set-cookie"))


# ---------- CORS: only the dashboard may send the session cookie ----------

def _preflight(client: TestClient, origin: str):
    return client.options("/emails/e1/send", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": f"content-type,{CLIENT_HEADER.lower()}"})


def test_the_dashboard_origin_may_send_its_session_with_the_client_header(client):
    response = _preflight(client, "http://localhost:8090")
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8090"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize("origin", ["http://localhost:8080", "https://evil.example"])
def test_any_other_origin_never_gets_credentials(client, origin):
    response = _preflight(client, origin)
    assert response.headers.get("access-control-allow-credentials") is None


def test_a_refused_sign_up_says_so_instead_of_a_generic_failure(client):
    response = client.get("/auth/callback?error=access_denied&error_description=Signups+not+allowed+for+this+instance",
                          follow_redirects=False)
    assert response.headers["location"] == "http://localhost:8090/signin?error=sign_in_not_allowed"


def test_every_failed_callback_logs_why(client, caplog):
    caplog.set_level("WARNING")
    client.get("/auth/callback?code=abc", follow_redirects=False)
    client.get("/auth/callback?error=server_error&error_description=Unable+to+exchange+external+code",
               follow_redirects=False)
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "no PKCE verifier cookie" in logged
    assert "Unable to exchange external code" in logged
