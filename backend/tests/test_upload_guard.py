"""Input limits on the ingestion routes (audit OWASP API8).

Before these, POST /documents/upload read the whole body into memory with no cap and trusted
the .pdf extension, so an oversized or mislabeled file reached the parser.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.constants import MAX_PASTE_CHARS, MAX_UPLOAD_BYTES, PDF_MAGIC
from app.main import app

TOKEN = "test-token-not-a-real-secret"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
UPLOAD_PATH = "/documents/upload"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BACKEND_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


def test_oversized_upload_is_refused(client):
    oversized = PDF_MAGIC + b"x" * MAX_UPLOAD_BYTES
    res = client.post(
        UPLOAD_PATH, files={"file": ("big.pdf", oversized, "application/pdf")}, headers=AUTH
    )
    assert res.status_code == 413


def test_non_pdf_content_renamed_to_pdf_is_refused(client):
    disguised = b"MZ\x90\x00executable payload"
    res = client.post(
        UPLOAD_PATH, files={"file": ("payload.pdf", disguised, "application/pdf")}, headers=AUTH
    )
    assert res.status_code == 400


def test_non_pdf_extension_is_refused(client):
    res = client.post(
        UPLOAD_PATH, files={"file": ("notes.txt", b"hello", "text/plain")}, headers=AUTH
    )
    assert res.status_code == 400


def test_oversized_paste_is_refused(client):
    body = {"title": "big", "text": "x" * (MAX_PASTE_CHARS + 1)}
    assert client.post("/documents", json=body, headers=AUTH).status_code == 422
