"""Uploaded documents are masked before they are stored or embedded, and never stored unmasked.

Email content is masked at ingest by the listener; documents went straight into Supabase and the
embedding model with every name and phone number in them.
"""

import asyncio
import json

import httpx
import pytest

from app.core.ownership import EVERYTHING
from app.rag import ingest, mask
from tests.conftest import AUTH_HEADERS as AUTH

POLICY = "Leave requests go to Siti Aminah on 012-345 6789 or hr@corp.com.my. Apply 3 days ahead."


def _presidio(monkeypatch, handler):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(mask.httpx, "AsyncClient", lambda **kw: real_client(transport=transport))


def _finds_the_name(request: httpx.Request) -> httpx.Response:
    """A stand-in analyzer that reports one PERSON span, where the name sits in the posted text."""
    text = json.loads(request.read())["text"]
    position = text.find("Siti Aminah")
    hits = [] if position < 0 else [{"entity_type": "PERSON", "start": position,
                                     "end": position + len("Siti Aminah"), "score": 0.9}]
    return httpx.Response(200, json=hits)


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("presidio down")


def test_names_and_fixed_formats_are_masked(monkeypatch, test_settings):
    _presidio(monkeypatch, _finds_the_name)
    masked = asyncio.run(mask.mask_document(POLICY))
    assert "Siti Aminah" not in masked and "012-345 6789" not in masked and "hr@corp" not in masked
    assert "Apply 3 days ahead." in masked


def test_a_document_is_refused_rather_than_stored_unmasked_when_presidio_is_down(monkeypatch, test_settings):
    _presidio(monkeypatch, _down)

    def must_not_store():
        raise AssertionError("an unmasked document reached the database")

    monkeypatch.setattr(ingest, "get_sessionmaker", must_not_store)
    with pytest.raises(mask.DocumentMaskingError):
        asyncio.run(ingest.ingest_text("paste://leave", "Leave", POLICY, scope=EVERYTHING))


def test_the_paste_route_answers_503_when_masking_is_unavailable(api_client, monkeypatch):
    _presidio(monkeypatch, _down)
    response = api_client.post("/documents", json={"title": "Leave", "text": POLICY}, headers=AUTH)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "masking_unavailable"
