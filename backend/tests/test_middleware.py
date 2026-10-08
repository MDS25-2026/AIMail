"""Request id, security headers and the generation rate limit, observed from outside."""


import pytest

from app.core.constants import GENERATION_RATE_LIMIT
from app.core.middleware import REQUEST_ID_HEADER, incoming_request_id
from app.core.ratelimit import rate_limit_generation
from tests.conftest import AUTH_HEADERS as AUTH


def test_every_response_carries_a_request_id_and_no_store(api_client):
    response = api_client.get("/emails/not-a-uuid", headers=AUTH)
    assert response.headers[REQUEST_ID_HEADER]
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_a_rejected_request_still_gets_the_headers(api_client):
    response = api_client.get("/emails")
    assert response.status_code == 401
    assert response.headers["X-Frame-Options"] == "DENY"


def test_the_demo_page_may_run_its_inline_script(api_client):
    csp = api_client.get("/").headers["Content-Security-Policy"]
    assert "script-src 'unsafe-inline'" in csp


def test_a_safe_incoming_request_id_is_kept(api_client):
    response = api_client.get("/", headers={REQUEST_ID_HEADER: "trace-123"})
    assert response.headers[REQUEST_ID_HEADER] == "trace-123"


@pytest.mark.parametrize("hostile", ["a\nFAKE LOG LINE", "x" * 65, "<script>", ""])
def test_an_unsafe_incoming_request_id_is_replaced(hostile):
    assert incoming_request_id(hostile) != hostile


@pytest.fixture
def generation_limit():
    rate_limit_generation.reset()
    yield
    rate_limit_generation.reset()


def test_model_spending_routes_are_throttled(api_client, generation_limit):
    # An empty body fails validation after the limiter has already counted the request.
    for _ in range(GENERATION_RATE_LIMIT):
        assert api_client.post("/search", json={}, headers=AUTH).status_code == 422
    assert api_client.post("/search", json={}, headers=AUTH).status_code == 429


def test_a_decoded_newline_in_the_path_cannot_forge_a_log_line():
    from app.core.middleware import printable

    assert "\n" not in printable("/emails/x\nINFO forged admin login")
