"""The mailbox owner comes from the Gmail account AIMail is connected to, not a setting.

Stage 1 of ADR 0005 reads one mailbox; whoever signs in with that Google account sees its mail.
The backend already holds that account's Gmail login (it sends replies with it), so it asks Gmail
for the address instead of making someone type it into .env.
"""

import asyncio

import httpx
import pytest

from app.core import mailbox, supabase_auth
from app.core.auth import Principal
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _no_owner(monkeypatch, test_settings):
    monkeypatch.setenv("MAILBOX_OWNER_EMAIL", "")
    get_settings.cache_clear()
    monkeypatch.setattr(mailbox, "_detected", "")


def test_the_gmail_account_is_the_owner_with_no_setting(monkeypatch):
    async def profile():
        return "Owner@Gmail.com"

    monkeypatch.setattr(mailbox, "gmail_address", profile)
    asyncio.run(mailbox.resolve_owner())
    assert Principal(email="owner@gmail.com").has_mailbox
    assert not Principal(email="someone@gmail.com").has_mailbox


def test_an_unreachable_gmail_falls_back_to_the_setting_if_there_is_one(monkeypatch, caplog):
    async def unreachable():
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(mailbox, "gmail_address", unreachable)
    monkeypatch.setenv("MAILBOX_OWNER_EMAIL", "fallback@gmail.com")
    get_settings.cache_clear()
    caplog.set_level("WARNING")
    asyncio.run(mailbox.resolve_owner())
    assert mailbox.owner() == "fallback@gmail.com"
    assert "could not read the Gmail address" in caplog.text


def test_with_neither_no_signed_in_user_sees_mail():
    assert mailbox.owner() == ""
    assert not Principal(email="anyone@gmail.com").has_mailbox


def test_an_invalid_supabase_key_is_a_server_problem_not_a_bad_sign_in():
    response = httpx.Response(401, json={"message": "Invalid API key"})
    with pytest.raises(supabase_auth.SupabaseNotConfiguredError):
        supabase_auth.session_from(response)


def test_a_refused_code_is_still_a_bad_sign_in():
    response = httpx.Response(400, json={"error": "invalid_grant"})
    with pytest.raises(supabase_auth.InvalidGrantError):
        supabase_auth.session_from(response)
