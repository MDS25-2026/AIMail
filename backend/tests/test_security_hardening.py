"""Fixes from the 2026-10-21 security review (specs/features/security-hardening-2026-10.md)."""

import asyncio
import base64
import email
import logging

from fastapi.testclient import TestClient

from app import gmail_send, sign_in
from app.core import supabase_auth
from app.core.supabase_auth import Session
from app.main import app
from tests.conftest import agent_client
from tests.test_account import _signed_in, calls  # noqa: F401  (fixture)


def _sent_to(monkeypatch, reply_to: str) -> str:
    async def headers(_client, _gmail_id, _names, _owner):
        return {"from": "boss@corp.example", "reply-to": reply_to, "subject": "Invoice",
                "message-id": "<a@b>", "threadid": "abc"}

    monkeypatch.setattr(gmail_send, "message_headers", headers)
    target = asyncio.run(gmail_send._reply_target(None, "gid", "boss@corp.example", "Invoice", None))
    return email.message_from_bytes(base64.urlsafe_b64decode(gmail_send._build_raw(target, "Hi")))["To"]


def test_a_reply_to_listing_several_addresses_sends_the_reply_to_the_sender_alone(monkeypatch):
    assert _sent_to(monkeypatch, "boss@corp.example, thief@evil.example") == "boss@corp.example"


def test_a_single_reply_to_is_still_honoured(monkeypatch):
    assert _sent_to(monkeypatch, "Support <support@corp.example>") == "Support <support@corp.example>"


def test_signing_out_with_only_the_refresh_cookie_left_still_revokes_the_session(api_client, monkeypatch):
    revoked = []

    async def refresh(token):
        return Session(access_token=f"access-for-{token}", refresh_token="new", expires_in=3600)

    async def revoke(token):
        revoked.append(token)

    monkeypatch.setattr(supabase_auth, "refresh_session", refresh)
    monkeypatch.setattr(supabase_auth, "revoke", revoke)
    response = api_client.delete("/auth/session", headers={"X-AIMail-Client": "1"},
                                 cookies={sign_in.REFRESH_COOKIE: "week-old"})
    assert response.status_code == 204 and revoked == ["access-for-week-old"]


def test_a_non_ascii_bearer_token_is_refused_not_a_server_error(api_client):
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/emails", headers={"Authorization": b"Bearer \xc3\xa9"}).status_code == 401


def test_a_non_ascii_agent_token_is_refused_not_a_server_error():
    client = TestClient(agent_client().app, raise_server_exceptions=False)
    assert client.post("/compose", headers={"X-AIMail-Agent-Token": b"\xc3\xa9"}, json={}).status_code == 403


def test_a_sign_in_error_in_the_url_cannot_forge_a_log_line(api_client, caplog):
    caplog.set_level(logging.WARNING)
    api_client.get("/auth/callback", params={"error": "x\n2026-10-21 INFO forged line"}, follow_redirects=False)
    assert not any("\n2026-10-21" in record.getMessage() for record in caplog.records)


def test_opening_an_email_from_a_cookie_session_needs_the_dashboards_header(calls):  # noqa: F811
    response = _signed_in().get("/emails/00000000-0000-4000-8000-000000000001")
    assert response.status_code == 403 and response.json()["error"]["code"] == "client_header_missing"
