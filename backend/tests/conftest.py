"""Shared fixtures for the API tests.

Tests never read a .env: AIMAIL_ENV_FILE is emptied before the app is imported, so every setting a
test needs comes from the environment it sets here, exactly as in CI.

The database URL is deliberately a throwaway: no test here should reach the database, and if
one does, the app's handler turns the connection error into a clean 503 rather than a crash.
"""

import os

os.environ["AIMAIL_ENV_FILE"] = ""  # before any app import reads settings

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_sessionmaker
from app.main import app

API_TOKEN = "test-token-not-a-real-secret"
AUTH_HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


@pytest.fixture(autouse=True)
def fresh_settings():
    """Each test reads settings, and builds its engine, from its own environment, never a previous test's."""
    _clear_caches()
    yield
    _clear_caches()


def _clear_caches() -> None:
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()


@pytest.fixture
def test_settings(monkeypatch):
    """Required settings for any test that reads `get_settings()`, so it passes without a `.env`."""
    monkeypatch.setenv("BACKEND_API_TOKEN", API_TOKEN)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused:unused@127.0.0.1:5432/unused")
    monkeypatch.setenv("GOOGLE_API_KEY", "unused-in-tests")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def api_client(test_settings):
    return TestClient(app)
