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

from app import dashboard
from app.core.config import get_settings
from app.core.ratelimit import MemoryCounters, all_limiters
from app.db.session import get_engine, get_sessionmaker
from app.main import app
from app.personalisation import DEFAULT_POLICY

API_TOKEN = "test-token-not-a-real-secret"
AUTH_HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


REAL_POLICY_FOR = dashboard._policy_for


@pytest.fixture(autouse=True)
def default_priority_policy(monkeypatch):
    """Detail views read the owner's priority rules from the database; unit tests have none, so they get the
    neutral policy. tests/test_detail_priority.py checks the real lookup."""

    async def neutral(_message):
        return DEFAULT_POLICY

    monkeypatch.setattr(dashboard, "_policy_for", neutral)


@pytest.fixture(autouse=True)
def memory_rate_limits():
    """Counters in memory, fresh per test: tests have no database (production uses Postgres)."""
    for limiter in all_limiters():
        limiter.store = MemoryCounters()


@pytest.fixture(autouse=True)
def fresh_settings():
    """Each test reads settings, and builds its engine, from its own environment, never a previous test's."""
    _clear_caches()
    yield
    os.environ.pop("AGENT_TOKEN", None)  # set by agent_client(); never carried into the next test
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


AGENT_TOKEN = "test-agent-token"


def agent_client() -> TestClient:
    """The agent as the backend calls it: with the service token (app/core/agent_auth.py)."""
    os.environ["AGENT_TOKEN"] = AGENT_TOKEN
    get_settings.cache_clear()
    import email_agent

    return TestClient(email_agent.app, headers={"X-AIMail-Agent-Token": AGENT_TOKEN})
