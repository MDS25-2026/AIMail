"""Auth gate on the API (audit OWASP API1).

The property under test is that no unauthenticated caller can reach a mutating route —
POST /emails/{id}/send dispatches a real Gmail reply, so this is the load-bearing check. Signed-in
users (cookie or Supabase bearer) are covered in test_user_auth.py; these are the shared-token paths.
Authorized requests are asserted only to get *past* auth (not 401/503): what happens after
belongs to the route's own tests and would need a database here.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests.conftest import API_TOKEN as TOKEN

SEND_PATH = "/emails/abc123/send"
SEND_BODY = {"draft": "hello"}


@pytest.fixture
def client(api_client):
    return api_client


def test_send_without_a_token_is_rejected(client):
    assert client.post(SEND_PATH, json=SEND_BODY).status_code == 401


def test_send_with_a_wrong_token_is_rejected(client):
    res = client.post(SEND_PATH, json=SEND_BODY, headers={"Authorization": f"Bearer {TOKEN}x"})
    assert res.status_code == 401


def test_reading_the_inbox_requires_a_token(client):
    # Read routes return masked email content, so they are gated too, not just mutations.
    assert client.get("/emails").status_code == 401


def test_send_with_the_right_token_passes_the_auth_gate(client):
    res = client.post(SEND_PATH, json=SEND_BODY, headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code != 401


def test_demo_page_stays_open_as_the_liveness_check(client):
    assert client.get("/").status_code != 401


def test_an_unset_shared_token_never_lets_a_request_through(api_client, monkeypatch):
    # Empty must not mean "auth off": with no token configured, a script's bearer is treated as a
    # user session and fails verification, and a bare request is still signed out.
    monkeypatch.setenv("BACKEND_API_TOKEN", "")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        assert client.post(SEND_PATH, json=SEND_BODY).status_code == 401
        assert client.post(SEND_PATH, json=SEND_BODY,
                           headers={"Authorization": "Bearer "}).status_code in (401, 403)
    finally:
        get_settings.cache_clear()
