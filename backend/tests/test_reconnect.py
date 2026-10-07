"""Expired Google access (specs/features/per-user-mailboxes.md): mark it, say so, never guess."""

import asyncio
import subprocess
import sys
from uuid import UUID

import httpx
import pytest

from app import gmail_send

ALICE = UUID("aaaaaaaa-0000-4000-8000-000000000001")


def _token_endpoint(status: int, body: dict) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body)))


@pytest.fixture
def marked(monkeypatch):
    seen = []

    async def mark(user_id):
        seen.append(user_id)

    async def grant(_owner_id):
        return {"client_id": "c", "client_secret": "s", "refresh_token": "r"}

    monkeypatch.setattr(gmail_send, "_mark_needs_reconnect", mark)
    monkeypatch.setattr(gmail_send, "_refresh_grant", grant)
    gmail_send._cached_tokens.clear()
    return seen


def test_a_refused_token_marks_the_user_to_reconnect_and_says_why(marked):
    client = _token_endpoint(400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
    with pytest.raises(gmail_send.GoogleAccessExpiredError):
        asyncio.run(gmail_send._access_token(client, ALICE))
    assert marked == [ALICE]


@pytest.mark.parametrize(("status", "body"), [(400, {"error": "invalid_request"}), (503, {"error": "unavailable"})])
def test_any_other_token_failure_does_not_ask_the_user_to_reconnect(marked, status, body):
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(gmail_send._access_token(_token_endpoint(status, body), ALICE))
    assert marked == []


def test_the_original_mailbox_is_never_marked(marked):
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(gmail_send._access_token(_token_endpoint(400, {"error": "invalid_grant"}), None))
    assert marked == []


def test_a_send_refused_for_expired_access_is_its_own_error(marked, monkeypatch):
    async def refused(*_args, **_kwargs):
        raise gmail_send.GoogleAccessExpiredError("expired")

    monkeypatch.setattr(gmail_send, "_reply_target", refused)
    with pytest.raises(gmail_send.AccessExpiredSendError):
        asyncio.run(gmail_send.send_reply("gm-1", "a@b.c", "Hi", "body", owner_id=ALICE))


@pytest.mark.parametrize("module", ["app.gmail_send", "app.connections", "app.core.mailbox"])
def test_each_mailbox_module_imports_on_its_own(module):
    # A cycle (gmail_send -> connections -> mailbox -> gmail_send) only shows when a script
    # imports one of them first; the app's own import order hid it.
    result = subprocess.run([sys.executable, "-c", f"import {module}"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
