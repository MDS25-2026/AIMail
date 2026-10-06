"""POST /emails/{id}/translate: masked text in, a checked translation out."""

import pytest

from app import dashboard
from app.plain_text import plain_text
from tests.conftest import AUTH_HEADERS as AUTH


def test_markup_becomes_prose_without_scripts_or_styles():
    html = "<html><head><style>p{}</style></head><body><p>Hi&nbsp;there</p><script>x()</script><div>Bye</div></body></html>"
    assert plain_text(html) == "Hi there\nBye"


def test_plain_text_is_untouched():
    assert plain_text("Line one\n\nLine two") == "Line one\n\nLine two"


def test_an_unknown_language_is_rejected(api_client):
    response = api_client.post("/emails/x/translate", json={"language": "fr"}, headers=AUTH)
    assert response.status_code == 422


def test_a_bad_id_is_404(api_client, monkeypatch):
    response = api_client.post("/emails/not-a-uuid/translate", json={"language": "ms"}, headers=AUTH)
    assert response.status_code == 404


def test_an_unfaithful_translation_surfaces_as_422_with_its_code(api_client, monkeypatch):
    async def refused(message_id: str, language: str, *, scope):
        raise dashboard.TranslationError("translation_unfaithful", 422)

    monkeypatch.setattr("app.main.translate_email", refused)
    response = api_client.post("/emails/x/translate", json={"language": "ms"}, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["detail"] == "translation_unfaithful"


@pytest.fixture(autouse=True)
def _reset_limit():
    from app.core.ratelimit import rate_limit_generation

    rate_limit_generation.reset()
    yield
    rate_limit_generation.reset()


@pytest.mark.parametrize("body, expected", [
    (b"not json", "agent_error"),
    (b'{"detail": {"code": "translation_unfaithful"}}', "translation_unfaithful"),
    (b'{"detail": "gemini_deadline_exceeded"}', "gemini_deadline_exceeded"),
    (b'{"detail": [{"msg": "too long", "input": "the whole masked body"}]}', "agent_error"),
])
def test_agent_errors_become_codes_and_never_echo_the_body(body, expected):
    import httpx

    assert dashboard._agent_error_code(httpx.Response(422, content=body)) == expected
