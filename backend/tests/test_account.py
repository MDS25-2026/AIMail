"""Settings > Account: disconnect Gmail and delete the account (per-user mailboxes, step 5)."""

import time
from dataclasses import dataclass
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import account
from app.core import supabase_auth
from app.core.auth import SESSION_COOKIE
from app.core.config import get_settings
from app.main import app
from tests.conftest import AUTH_HEADERS

SUPABASE = "https://project.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())
ALICE = UUID("aaaaaaaa-0000-4000-8000-000000000001")


@dataclass(frozen=True)
class _SigningKey:
    key: object


class _FakeJwks:
    def get_signing_key_from_jwt(self, token):
        return _SigningKey(KEY.public_key())


@pytest.fixture
def calls(monkeypatch, test_settings):
    for name, value in (("SUPABASE_URL", SUPABASE), ("SUPABASE_ANON_KEY", "anon")):
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    monkeypatch.setattr(supabase_auth, "_jwks", lambda base: _FakeJwks())
    seen = []

    async def disconnect(user_id):
        seen.append(("disconnect", user_id))
        return account.Erased(messages=3)

    async def delete(user_id):
        seen.append(("delete", user_id))
        return account.Erased(messages=0, documents=1)

    monkeypatch.setattr(account, "disconnect_gmail", disconnect)
    monkeypatch.setattr(account, "delete_account", delete)
    return seen


def _signed_in() -> TestClient:
    claims = {"sub": str(ALICE), "email": "alice@gmail.com", "aud": "authenticated",
              "iss": f"{SUPABASE}/auth/v1", "exp": int(time.time()) + 600}
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, jwt.encode(claims, KEY, algorithm="ES256"))
    return client


def test_disconnecting_gmail_acts_for_the_signed_in_user_only(calls):
    response = _signed_in().delete("/account/gmail", headers={"X-AIMail-Client": "1"})
    assert response.status_code == 204 and calls == [("disconnect", ALICE)]


def test_a_cookie_request_without_the_client_header_is_refused(calls):
    assert _signed_in().delete("/account").status_code == 403
    assert calls == []


def test_deleting_the_account_signs_the_user_out(calls):
    response = _signed_in().delete("/account", headers={"X-AIMail-Client": "1"})
    assert response.status_code == 204 and calls == [("delete", ALICE)]
    assert SESSION_COOKIE in response.headers.get("set-cookie", "")


def test_a_script_has_no_account_to_delete(calls):
    response = TestClient(app).delete("/account", headers=AUTH_HEADERS)
    assert response.status_code == 403 and response.json()["detail"] == "account_only"
    assert calls == []


def test_disconnecting_with_nothing_connected_says_so(calls, monkeypatch):
    async def nothing(_user_id):
        raise account.NotConnectedError("none")

    monkeypatch.setattr(account, "disconnect_gmail", nothing)
    response = _signed_in().delete("/account/gmail", headers={"X-AIMail-Client": "1"})
    assert response.status_code == 404 and response.json()["detail"] == "not_connected"


def test_a_deletion_that_stops_part_way_says_to_try_again_and_keeps_the_session(calls, monkeypatch):
    async def partial(_user_id):
        raise account.AccountDeletionError("Supabase unreachable")

    monkeypatch.setattr(account, "delete_account", partial)
    response = _signed_in().delete("/account", headers={"X-AIMail-Client": "1"})
    assert response.status_code == 502 and response.json()["detail"] == "account_not_fully_deleted"
    assert SESSION_COOKIE not in response.headers.get("set-cookie", "")


# ---------- Holding reply settings: who may call, and what is refused ----------

def test_a_script_has_no_holding_reply_settings(calls):
    assert TestClient(app).get("/settings/holding-reply", headers=AUTH_HEADERS).status_code == 403


def test_settings_that_could_never_work_are_refused_with_their_code(calls):
    response = _signed_in().put("/settings/holding-reply", headers={"X-AIMail-Client": "1"},
                                json={"enabled": True, "templates": {"en": "Back on {return_date}"}})
    assert response.status_code == 422 and response.json()["detail"] == "return_date_needs_leave"
