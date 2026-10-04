"""A reply goes out from the mailbox the email arrived in (per-user mailboxes, step 3).

A connected user's mail is answered with their own refresh token, unsealed in memory and refreshed
with the Google OAuth client that issued it. The original single mailbox keeps token.json. A user
who let AIMail read but not send is told so before anything is claimed.
"""

import asyncio
from uuid import UUID, uuid4

import httpx
import pytest

from app import dashboard, gmail_send
from app.core import token_crypt
from app.core.config import get_settings
from app.core.ownership import EVERYTHING
from app.db.models import MaskingStatus, Message

ALICE = UUID("aaaaaaaa-0000-4000-8000-000000000001")
KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="


@pytest.fixture
def google(monkeypatch, test_settings):
    for name, value in (("TOKEN_ENCRYPTION_KEY", KEY), ("GOOGLE_OAUTH_CLIENT_ID", "web-client"),
                        ("GOOGLE_OAUTH_CLIENT_SECRET", "web-secret")):
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    gmail_send._cached_tokens.clear()
    sealed = token_crypt.seal("1//alice-refresh", str(ALICE))

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def scalar(self, _statement):
            return sealed

    monkeypatch.setattr(gmail_send, "get_sessionmaker", lambda: lambda: _Session())
    monkeypatch.setattr(gmail_send, "_load_creds", lambda: (
        {"client_id": "desktop-client", "client_secret": "desktop-secret"}, {"refresh_token": "1//legacy"}))
    refreshes: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        form = dict(httpx.QueryParams(request.content.decode()))
        refreshes.append(form)
        return httpx.Response(200, json={"access_token": f"access-for-{form['refresh_token']}", "expires_in": 3600})

    yield refreshes, httpx.AsyncClient(transport=httpx.MockTransport(handle))
    gmail_send._cached_tokens.clear()


def test_a_connected_users_mail_is_sent_with_their_own_token_and_the_web_client(google):
    refreshes, client = google
    token = asyncio.run(gmail_send._access_token(client, ALICE))
    assert token == "access-for-1//alice-refresh"
    assert refreshes[0]["client_id"] == "web-client" and refreshes[0]["client_secret"] == "web-secret"


def test_the_original_mailbox_still_uses_token_json(google):
    refreshes, client = google
    assert asyncio.run(gmail_send._access_token(client, None)) == "access-for-1//legacy"
    assert refreshes[0]["client_id"] == "desktop-client"


def test_each_mailbox_has_its_own_cached_token(google):
    refreshes, client = google

    async def both():
        return (await gmail_send._access_token(client, ALICE), await gmail_send._access_token(client, None),
                await gmail_send._access_token(client, ALICE))

    alice, legacy, alice_again = asyncio.run(both())
    assert alice == alice_again != legacy
    assert len(refreshes) == 2


def test_without_the_google_client_settings_sending_fails_cleanly(google, monkeypatch):
    _refreshes, client = google
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    get_settings.cache_clear()
    with pytest.raises(gmail_send.GmailAccessError, match="GOOGLE_OAUTH_CLIENT_ID"):
        asyncio.run(gmail_send._access_token(client, ALICE))


def test_a_send_with_unusable_credentials_is_an_ordinary_send_failure(google, monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    get_settings.cache_clear()
    with pytest.raises(gmail_send.SendError) as caught:
        asyncio.run(gmail_send.send_reply(None, "a@b.com", "Hi", "Body", owner_id=ALICE))
    assert "1//alice-refresh" not in str(caught.value)


def test_a_user_who_granted_read_only_is_refused_before_anything_is_claimed(monkeypatch):
    message = Message(id=uuid4(), user_id=ALICE, masking_status=MaskingStatus.COMPLETE)
    claimed = []

    async def load(pk, scope):
        return message

    async def can_send(user_id):
        return False

    async def claim(pk):
        claimed.append(pk)
        return True

    monkeypatch.setattr(dashboard, "_load", load)
    monkeypatch.setattr(dashboard.connections, "can_send", can_send)
    monkeypatch.setattr(dashboard, "_claim_send", claim)
    with pytest.raises(dashboard.SendRejectedError) as caught:
        asyncio.run(dashboard.approve_and_send(str(message.id), "Thanks", scope=EVERYTHING))
    assert (caught.value.code, caught.value.status_code) == (dashboard.SendErrorCode.SEND_NOT_GRANTED, 403)
    assert claimed == []
