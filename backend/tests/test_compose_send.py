"""A new email goes out as its own thread, to the addresses as typed (specs/features/compose.md)."""

import asyncio
import base64
import email
import json
from email import policy
from uuid import uuid4

import httpx
import pytest

from app import gmail_send
from tests.conftest import AUTH_HEADERS

OWNER = uuid4()


@pytest.fixture
def gmail(monkeypatch):
    monkeypatch.setattr(gmail_send, "_cached_tokens", {OWNER: ("token", float("inf"))})
    state: dict = {"sent": None}

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/send"):
            state["sent"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "new-1", "threadId": "thread-new"})
        return httpx.Response(200, json={"payload": {"headers": [{"name": "Message-ID", "value": "<n@gmail.com>"}]}})

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(gmail_send.httpx, "AsyncClient", lambda **kw: real_client(transport=transport))
    return state


def _send() -> gmail_send.SentReply:
    return asyncio.run(gmail_send.send_new(["Harith Zulkifli <harith@keris.com.my>"], ["ops@keris.com.my"],
                                           "Credit note for the pallet wrap", "Dear Harith,\n\nBy Friday.",
                                           owner_id=OWNER))


def test_a_new_email_starts_its_own_thread_under_its_own_subject(gmail):
    sent = _send()
    mime = email.message_from_bytes(base64.urlsafe_b64decode(gmail["sent"]["raw"]), policy=policy.default)
    assert "threadId" not in gmail["sent"]
    assert mime["Subject"] == "Credit note for the pallet wrap"
    assert mime["To"] == "Harith Zulkifli <harith@keris.com.my>" and mime["Cc"] == "ops@keris.com.my"
    assert mime["In-Reply-To"] is None and mime["References"] is None
    assert sent.gmail_id == "new-1" and sent.thread_id == "thread-new" and sent.message_id == "<n@gmail.com>"


def test_compose_is_for_a_signed_in_person_not_a_script(api_client):
    response = api_client.get("/compose", headers=AUTH_HEADERS)
    assert response.status_code == 403 and response.json()["error"]["code"] == "account_only"
