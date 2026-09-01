"""Shared fixtures for the API tests.

`Settings` has required fields that normally come from the repo-root `.env`. CI has no such
file, so any test that clears the settings cache must supply them through the environment or
`get_settings()` raises before the request is ever handled — which is exactly how these tests
passed locally and failed in CI.

The database URL is deliberately a throwaway: no test here should reach the database, and if
one does, the app's handler turns the connection error into a clean 503 rather than a crash.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

API_TOKEN = "test-token-not-a-real-secret"
AUTH_HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setenv("BACKEND_API_TOKEN", API_TOKEN)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused:unused@127.0.0.1:5432/unused")
    monkeypatch.setenv("GEMINI_API_KEY", "unused-in-tests")
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()
