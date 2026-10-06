"""Per-IP rate limit on the ingestion routes (audit OWASP API8).

Size caps bound one request; this bounds how many a client may make.

These drive the routes with a payload that is rejected before any database work, so the test
measures the limiter rather than the ingestion pipeline. The quota is spent either way: the
dependency runs ahead of the route body, so even a request destined for 400 consumes a slot.
The window is process-local state, so each test clears it to stay order-independent.
"""

import pytest

from app.core import ratelimit
from app.core.constants import INGEST_RATE_LIMIT, INGEST_RATE_WINDOW_SECONDS
from app.core.ratelimit import _hits
from tests.conftest import AUTH_HEADERS as AUTH

UPLOAD_PATH = "/documents/upload"
# Not a PDF: rejected at the magic-bytes check, so no request reaches the database.
NOT_A_PDF = {"file": ("notes.pdf", b"plain text, not a pdf", "application/pdf")}


@pytest.fixture
def client(api_client):
    _hits.clear()
    yield api_client
    _hits.clear()


def test_requests_within_the_quota_are_not_throttled(client):
    for _ in range(INGEST_RATE_LIMIT):
        assert client.post(UPLOAD_PATH, files=NOT_A_PDF, headers=AUTH).status_code == 400


def test_a_burst_past_the_quota_is_throttled(client):
    for _ in range(INGEST_RATE_LIMIT):
        client.post(UPLOAD_PATH, files=NOT_A_PDF, headers=AUTH)

    res = client.post(UPLOAD_PATH, files=NOT_A_PDF, headers=AUTH)
    assert res.status_code == 429
    assert res.headers["Retry-After"] == str(INGEST_RATE_WINDOW_SECONDS)


def test_the_quota_frees_up_once_the_window_passes(client, monkeypatch):
    for _ in range(INGEST_RATE_LIMIT):
        client.post(UPLOAD_PATH, files=NOT_A_PDF, headers=AUTH)
    assert client.post(UPLOAD_PATH, files=NOT_A_PDF, headers=AUTH).status_code == 429

    # Jump past the window instead of sleeping through it.
    real_monotonic = ratelimit.time.monotonic
    monkeypatch.setattr(
        ratelimit.time, "monotonic", lambda: real_monotonic() + INGEST_RATE_WINDOW_SECONDS + 1
    )
    assert client.post(UPLOAD_PATH, files=NOT_A_PDF, headers=AUTH).status_code == 400


def test_unauthenticated_callers_are_rejected_before_the_quota_is_spent(client):
    # Auth runs ahead of the limiter, so an anonymous flood cannot exhaust a real client's window.
    for _ in range(INGEST_RATE_LIMIT + 5):
        assert client.post(UPLOAD_PATH, files=NOT_A_PDF).status_code == 401
    assert client.post(UPLOAD_PATH, files=NOT_A_PDF, headers=AUTH).status_code == 400
