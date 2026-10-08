"""A reply is sent at most once, and only a draft that is safe to send is accepted.

Gmail can accept a send and the reply still be lost on the way back (a read timeout, a cut
connection, an unreadable body). Treating that as "not sent" released the claim and invited a second
copy. Failures are now split by whether Gmail could have acted on the request.
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from app import dashboard, gmail_send
from app.core.ownership import EVERYTHING
from app.db.models import MaskingStatus, Message
from tests.conftest import AUTH_HEADERS as AUTH

ORIGINAL = {"threadId": "t-1", "payload": {"headers": [
    {"name": "Subject", "value": "Invoice"},
    {"name": "From", "value": "a@example.com"},
    {"name": "Message-Id", "value": "<orig@example.com>"},
]}}


def _gmail(monkeypatch, on_send):
    """Serve the original from Gmail and let `on_send` decide what the POST does."""
    monkeypatch.setattr(gmail_send, "_cached_tokens", {None: ("token", float("inf"))})

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/send"):
            return on_send(request)
        return httpx.Response(200, json=ORIGINAL)

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(gmail_send.httpx, "AsyncClient", lambda **kw: real_client(transport=transport))


def _send():
    return asyncio.run(gmail_send.send_reply("orig-1", "a@example.com", "Invoice", "Thanks.", owner_id=None))


def _raise(error):
    def on_send(request):
        raise error
    return on_send


@pytest.mark.parametrize("on_send", [
    _raise(httpx.ReadTimeout("no answer")),
    _raise(httpx.RemoteProtocolError("connection cut")),
    lambda request: httpx.Response(200, content=b"<html>not json</html>"),
])
def test_a_send_gmail_may_have_accepted_has_an_unknown_outcome(monkeypatch, on_send):
    _gmail(monkeypatch, on_send)
    with pytest.raises(gmail_send.SendOutcomeUnknownError):
        _send()


@pytest.mark.parametrize("on_send", [
    _raise(httpx.ConnectError("refused")),
    lambda request: httpx.Response(500, json={"error": "backend"}),
    lambda request: httpx.Response(400, json={"error": "bad"}),
])
def test_a_send_gmail_never_accepted_is_an_ordinary_failure(monkeypatch, on_send):
    _gmail(monkeypatch, on_send)
    with pytest.raises(gmail_send.SendError):
        _send()


def _message(**fields) -> Message:
    defaults = {"id": uuid4(), "from_addr": "a@b.c", "subject": "Hi",
                "masking_status": MaskingStatus.COMPLETE,
                "created_at": datetime(2026, 10, 4, tzinfo=timezone.utc)}
    return Message(**(defaults | fields))


@pytest.fixture
def harness(monkeypatch):
    """The send path with its database and Gmail calls replaced by recorders."""
    state = {"message": _message(), "claimed": 0, "released": 0, "sent": 0, "audits": [],
             "send_error": None}

    async def load(pk, scope):
        return state["message"]

    async def claim(pk):
        state["claimed"] += 1
        return True

    async def release(pk):
        state["released"] += 1

    async def send_reply(*_args, **_kwargs):
        state["sent"] += 1
        if state["send_error"]:
            raise state["send_error"]
        return gmail_send.SentReply(gmail_id="g", thread_id="t", message_id="<m>")

    async def audit(action, *, success=True, user_id=None, **fields):
        state["audits"].append((action, success))

    async def mark_unknown(_table, row_id):
        state["marked_unknown"] = row_id

    for name, value in (("_load", load), ("_claim_send", claim), ("_release_send_claim", release),
                        ("send_reply", send_reply), ("audit", audit), ("mark_outcome_unknown", mark_unknown)):
        monkeypatch.setattr(dashboard, name, value)
    return state


def _approve(state, draft="Thanks, paid."):
    return asyncio.run(dashboard.approve_and_send(str(state["message"].id), draft, scope=EVERYTHING))


def test_an_unknown_outcome_keeps_the_claim_so_it_is_never_sent_twice(harness):
    harness["send_error"] = gmail_send.SendOutcomeUnknownError("read timeout")
    with pytest.raises(gmail_send.SendOutcomeUnknownError):
        _approve(harness)
    assert harness["released"] == 0
    assert ("send_outcome_unknown", False) in harness["audits"]
    # Marked, so the reconciler settles it against Gmail later.
    assert harness["marked_unknown"] == harness["message"].id


def test_an_ordinary_failure_still_releases_the_claim(harness):
    harness["send_error"] = gmail_send.SendError("refused")
    with pytest.raises(gmail_send.SendError):
        _approve(harness)
    assert harness["released"] == 1


def test_a_draft_with_a_redaction_marker_is_refused_before_anything_is_claimed(harness):
    with pytest.raises(dashboard.SendRejectedError) as caught:
        _approve(harness, "Hi [Redacted], your number is [PHONE_REDACTED].")
    assert (caught.value.code, caught.value.status_code) == (dashboard.ErrorCode.REDACTION_MARKERS, 422)
    assert harness["claimed"] == harness["sent"] == 0


def test_an_email_that_is_not_masked_cannot_be_replied_to(harness):
    harness["message"] = _message(masking_status=MaskingStatus.PENDING)
    with pytest.raises(dashboard.SendRejectedError) as caught:
        _approve(harness)
    assert (caught.value.code, caught.value.status_code) == (dashboard.ErrorCode.MASKING_PENDING, 409)
    assert harness["sent"] == 0


def test_an_empty_draft_is_refused_by_the_route(api_client):
    assert api_client.post("/emails/x/send", json={"draft": ""}, headers=AUTH).status_code == 422


def test_the_route_reports_an_unknown_outcome_distinctly(api_client, monkeypatch):
    async def unknown(*_args, **_kwargs):
        raise gmail_send.SendOutcomeUnknownError("read timeout")

    monkeypatch.setattr("app.main.approve_and_send", unknown)
    response = api_client.post("/emails/x/send", json={"draft": "Thanks."}, headers=AUTH)
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "send_outcome_unknown"


def test_the_route_reports_a_rejected_draft_with_its_code(api_client, monkeypatch):
    async def rejected(*_args, **_kwargs):
        raise dashboard.SendRejectedError(dashboard.ErrorCode.REDACTION_MARKERS, 422)

    monkeypatch.setattr("app.main.approve_and_send", rejected)
    response = api_client.post("/emails/x/send", json={"draft": "Hi [Redacted]"}, headers=AUTH)
    assert (response.status_code, response.json()["error"]["code"]) == (422, "redaction_markers")
