"""Signing in with Google also connects the user's own Gmail (per-user mailboxes, step 2).

The consent asks for Gmail read and send, offline, so Supabase returns a Google refresh token. The
backend checks which permissions were actually granted (Google lets people untick them), then
stores the token sealed. A failure here never blocks sign-in itself.
"""

import asyncio
import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import connections, sign_in
from app.core import supabase_auth
from app.core.config import get_settings
from app.main import app

SUPABASE = "https://project.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())
GMAIL_READ = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
USER_ID = "11111111-2222-3333-4444-555555555555"


def _access_token() -> str:
    claims = {"sub": USER_ID, "email": "new.user@gmail.com", "aud": "authenticated",
              "iss": f"{SUPABASE}/auth/v1", "exp": int(time.time()) + 600}
    return jwt.encode(claims, KEY, algorithm="ES256")


@pytest.fixture
def client(monkeypatch, test_settings):
    for name, value in (("SUPABASE_URL", SUPABASE), ("SUPABASE_ANON_KEY", "anon"),
                        ("DASHBOARD_URL", "http://localhost:8090"), ("ADMIN_COOKIE_SECURE", "false"),
                        ("TOKEN_ENCRYPTION_KEY", "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=")):
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    return TestClient(app)


def _supabase_answers(monkeypatch, body: dict):
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)
    monkeypatch.setattr(supabase_auth, "transport", httpx.MockTransport(respond))


def _session(**extra) -> dict:
    return {"access_token": _access_token(), "refresh_token": "r1", "expires_in": 3600,
            "user": {"id": USER_ID, "email": "new.user@gmail.com", "user_metadata": {"full_name": "New User"}},
            **extra}


@pytest.fixture
def stored(monkeypatch):
    saved = []

    async def store(user_id, email, refresh_token, scopes, display_name):
        saved.append({"user_id": user_id, "email": email, "token": refresh_token, "scopes": scopes,
                      "name": display_name})

    monkeypatch.setattr(connections, "store_connection", store)
    return saved


def _granted(monkeypatch, scopes: set[str]):
    async def granted(provider_token):
        return scopes
    monkeypatch.setattr(connections, "granted_scopes", granted)


def _callback(client):
    client.cookies.set(sign_in.VERIFIER_COOKIE, "the-verifier")
    return client.get("/auth/callback?code=abc", follow_redirects=False)


def test_sign_in_asks_google_for_gmail_offline_with_fresh_consent(client):
    query = parse_qs(urlparse(client.get("/auth/google/start", follow_redirects=False).headers["location"]).query)
    assert GMAIL_READ in query["scopes"][0] and GMAIL_SEND in query["scopes"][0]
    assert query["access_type"] == ["offline"] and query["prompt"] == ["consent"]


def test_a_granted_gmail_connection_is_stored_for_the_user(client, monkeypatch, stored):
    _supabase_answers(monkeypatch, _session(provider_token="ya29.x", provider_refresh_token="1//refresh"))
    _granted(monkeypatch, {GMAIL_READ, GMAIL_SEND})
    response = _callback(client)
    assert response.headers["location"] == "http://localhost:8090"
    assert stored == [{"user_id": USER_ID, "email": "new.user@gmail.com", "token": "1//refresh",
                       "scopes": sorted({GMAIL_READ, GMAIL_SEND}), "name": "New User"}]


def test_unticking_gmail_read_on_googles_screen_stores_nothing_but_still_signs_in(client, monkeypatch, stored):
    _supabase_answers(monkeypatch, _session(provider_token="ya29.x", provider_refresh_token="1//refresh"))
    _granted(monkeypatch, {"openid", "email"})
    assert _callback(client).headers["location"] == "http://localhost:8090"
    assert stored == []


def test_no_refresh_token_stores_nothing_and_logs_which_fields_came_back(client, monkeypatch, stored, caplog):
    _supabase_answers(monkeypatch, _session())
    caplog.set_level("WARNING")
    assert _callback(client).headers["location"] == "http://localhost:8090"
    assert stored == []
    assert "no Google refresh token" in caplog.text and "access_token" in caplog.text
    assert "the-verifier" not in caplog.text


def test_a_failure_to_store_never_blocks_sign_in(client, monkeypatch, caplog):
    _supabase_answers(monkeypatch, _session(provider_token="ya29.x", provider_refresh_token="1//refresh"))
    _granted(monkeypatch, {GMAIL_READ})

    async def broken(*_args):
        raise connections.ConnectionStoreError("database down")

    monkeypatch.setattr(connections, "store_connection", broken)
    caplog.set_level("WARNING")
    assert _callback(client).headers["location"] == "http://localhost:8090"
    assert "could not store the Gmail connection" in caplog.text
    assert "1//refresh" not in caplog.text


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _RecordingSession:
    def __init__(self, vault_rows=()):
        self.statements = []
        self.vault_rows = list(vault_rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    def begin(self):
        return self

    async def execute(self, statement):
        self.statements.append(str(statement))
        # The handover first asks for unowned vaults to re-seal; nothing else reads rows.
        return _Rows(self.vault_rows if str(statement).startswith("SELECT") else [])


def _stored_statements(monkeypatch, email: str, owner: str) -> list[str]:
    session = _RecordingSession()
    monkeypatch.setattr(connections, "get_sessionmaker", lambda: lambda: session)
    monkeypatch.setattr(connections.mailbox, "owner", lambda: owner)
    asyncio.run(connections.store_connection(USER_ID, email, "1//refresh", [GMAIL_READ], "New User"))
    return session.statements


def test_the_original_mailbox_connecting_takes_over_its_unowned_mail_and_documents(client, monkeypatch):
    statements = _stored_statements(monkeypatch, "Owner@Gmail.com", "owner@gmail.com")
    handed_over = [s for s in statements if s.startswith("UPDATE") and "user_id IS NULL" in s]
    assert len(handed_over) == 2


def test_handed_over_mail_keeps_its_details_readable(client, monkeypatch):
    from uuid import UUID

    from app.core import vault

    monkeypatch.setenv("PII_VAULT_KEY", "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=")
    get_settings.cache_clear()
    sealed = vault.seal_vault({"[PERSON_1]": "Aisyah"}, None, "gm-1")
    session = _RecordingSession(vault_rows=[("row-1", "gm-1", sealed)])
    updates = []
    original = session.execute

    async def execute(statement):
        if str(statement).startswith("UPDATE messages SET pii_vault"):
            updates.append(statement.compile().params["pii_vault"])
        return await original(statement)

    session.execute = execute
    monkeypatch.setattr(connections, "get_sessionmaker", lambda: lambda: session)
    monkeypatch.setattr(connections.mailbox, "owner", lambda: "owner@gmail.com")
    asyncio.run(connections.store_connection(USER_ID, "owner@gmail.com", "1//refresh", [GMAIL_READ], ""))
    assert len(updates) == 1
    assert vault.open_vault(updates[0], UUID(USER_ID), "gm-1") == {"[PERSON_1]": "Aisyah"}


def test_anyone_else_connecting_never_touches_unowned_rows(client, monkeypatch):
    statements = _stored_statements(monkeypatch, "new.user@gmail.com", "owner@gmail.com")
    assert not [s for s in statements if s.startswith("UPDATE")]


def test_the_google_account_name_becomes_the_profile_name_without_replacing_one_already_set(client, monkeypatch):
    statements = _stored_statements(monkeypatch, "new.user@gmail.com", "owner@gmail.com")
    profile = next(s for s in statements if "INSERT INTO user_profile" in s)
    assert "coalesce(user_profile.display_name, excluded.display_name)" in profile
