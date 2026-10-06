"""Access-token caching on the send path.

Refreshing on every send put a second round trip to Google in front of every reply, which was
most of the delay between clicking Approve & Send and the mail arriving. Tokens last about an
hour, so the refresh belongs behind a cache — provided a revoked token still recovers.
"""

import asyncio

import httpx
import pytest

from app import gmail_send


@pytest.fixture(autouse=True)
def _clear_cache():
    gmail_send._cached_token = None
    yield
    gmail_send._cached_token = None


@pytest.fixture
def fake_creds(monkeypatch):
    monkeypatch.setattr(
        gmail_send,
        "_load_creds",
        lambda: ({"client_id": "id", "client_secret": "secret"}, {"refresh_token": "refresh"}),
    )


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


def test_the_token_is_fetched_once_and_reused(fake_creds):
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"access_token": "abc", "expires_in": 3600})

    async def run() -> tuple[str, str]:
        async with _client(httpx.MockTransport(handle)) as client:
            return await gmail_send._access_token(client), await gmail_send._access_token(client)

    first, second = asyncio.run(run())

    assert first == second == "abc"
    assert len(calls) == 1, "a cached token must not cost a round trip"


def test_an_expired_token_is_refreshed(fake_creds):
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"access_token": "abc", "expires_in": 1})

    async def run() -> None:
        async with _client(httpx.MockTransport(handle)) as client:
            await gmail_send._access_token(client)
            # expires_in of 1s is inside the safety margin, so this must not reuse it.
            await gmail_send._access_token(client)

    asyncio.run(run())

    assert len(calls) == 2


def test_a_revoked_token_costs_one_retry_not_every_send(fake_creds, monkeypatch):
    monkeypatch.setattr(gmail_send, "_build_raw", lambda *a: "cmF3")
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "abc", "expires_in": 3600})
        # First send is rejected as if the token were revoked; the retry succeeds.
        sends = [p for p in seen if p.endswith("/send")]
        return httpx.Response(401 if len(sends) == 1 else 200, json={})

    transport = httpx.MockTransport(handle)
    # Capture the real class first: gmail_send.httpx *is* the httpx module, so referring to
    # httpx.AsyncClient inside the replacement would call the replacement.
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        gmail_send.httpx, "AsyncClient", lambda **kw: real_client(transport=transport)
    )

    asyncio.run(gmail_send.send_reply("a@b.com", "Subject", "Body"))

    assert len([p for p in seen if p.endswith("/send")]) == 2, "should retry exactly once"
