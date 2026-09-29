"""A reply joins the original's thread, under the original's real subject.

Gmail threads a sent message only when it carries the threadId, In-Reply-To/References, and a
Subject matching the original's. The stored subject is masked, so the real one is read from
Gmail at send time and never stored.
"""

import asyncio
import base64
import json

import httpx
import pytest

from app import gmail_send

ORIGINAL = {
    "threadId": "thread-7",
    "payload": {"headers": [
        {"name": "Subject", "value": "Invoice for Aisyah Rahman"},
        {"name": "From", "value": "Aisyah <aisyah@example.com>"},
        {"name": "Message-Id", "value": "<orig@mail.example.com>"},
        {"name": "References", "value": "<root@mail.example.com>"},
    ]},
}


@pytest.fixture(autouse=True)
def gmail(monkeypatch):
    monkeypatch.setattr(gmail_send, "_cached_token", ("token", float("inf")))
    state: dict = {"sent": None, "original_status": 200}

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/send"):
            state["sent"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "reply-1", "threadId": "thread-7"})
        if request.url.path.endswith("/reply-1"):
            headers = [{"name": "Message-ID", "value": "<reply@mail.gmail.com>"}]
            return httpx.Response(200, json={"payload": {"headers": headers}})
        return httpx.Response(state["original_status"], json=ORIGINAL)

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(gmail_send.httpx, "AsyncClient", lambda **kw: real_client(transport=transport))
    return state


def _sent_mime(state: dict) -> str:
    return base64.urlsafe_b64decode(state["sent"]["raw"]).decode()


def _send() -> gmail_send.SentReply:
    return asyncio.run(gmail_send.send_reply("orig-1", "fallback@example.com",
                                             "Invoice for [Redacted]", "Thanks, paid."))


def test_the_reply_carries_the_thread_id_and_references(gmail):
    _send()
    mime = _sent_mime(gmail)
    assert gmail["sent"]["threadId"] == "thread-7"
    assert "In-Reply-To: <orig@mail.example.com>" in mime
    assert "References: <root@mail.example.com> <orig@mail.example.com>" in mime


def test_the_reply_uses_the_real_subject_not_the_masked_one(gmail):
    _send()
    mime = _sent_mime(gmail)
    assert "Subject: Re: Invoice for Aisyah Rahman" in mime
    assert "[Redacted]" not in mime


def test_the_gmail_assigned_message_id_is_read_back(gmail):
    sent = _send()
    assert sent.message_id == "<reply@mail.gmail.com>"
    assert sent.thread_id == "thread-7"


def test_a_deleted_original_still_sends_standalone(gmail):
    gmail["original_status"] = 404
    _send()
    mime = _sent_mime(gmail)
    assert "threadId" not in gmail["sent"]
    assert "To: fallback@example.com" in mime
    assert "In-Reply-To" not in mime


def test_any_other_failure_reading_the_original_is_a_send_error(gmail):
    gmail["original_status"] = 500
    with pytest.raises(gmail_send.SendError):
        _send()
    assert gmail["sent"] is None, "nothing may be sent when the thread cannot be read"


def test_a_reply_to_header_wins_over_from(gmail, monkeypatch):
    headers = [*ORIGINAL["payload"]["headers"], {"name": "Reply-To", "value": "billing@example.com"}]
    monkeypatch.setitem(ORIGINAL, "payload", {"headers": headers})
    _send()
    assert "To: billing@example.com" in _sent_mime(gmail)
