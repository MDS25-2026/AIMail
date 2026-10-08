"""The host's probes reach both services without a session or a token, and readiness tells the truth."""

import asyncio
import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

import email_agent
from app.core import health
from app.core.logging_setup import JsonFormatter


def test_liveness_needs_no_sign_in(api_client):
    response = api_client.get("/healthz")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_a_service_is_not_ready_while_a_check_fails():
    async def down() -> bool:
        return False

    app = FastAPI()
    app.include_router(health.health_router({"database": down}))
    response = TestClient(app).get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "failed", "checks": {"database": "failed"}}


def test_an_unreachable_database_is_a_failed_check_not_a_crash(monkeypatch):
    def broken_engine():
        raise OSError("connection refused")

    monkeypatch.setattr(health, "get_engine", broken_engine)
    assert asyncio.run(health.database_answers()) is False


def test_the_agent_answers_its_probes_without_the_service_token(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_TOKEN", "a-token")
    email_agent.get_settings.cache_clear()
    client = TestClient(email_agent.app, client=("203.0.113.9", 50000))
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").json() == {"status": "ok", "checks": {"model": "ok"}}
    assert client.post("/translate", json={}).status_code == 403


def test_a_json_log_line_carries_the_same_fields_as_text():
    record = logging.LogRecord("app.x", logging.WARNING, __file__, 1, "draft failed with %s", ("code",), None)
    record.request_id = "r1"
    line = json.loads(JsonFormatter().format(record))
    assert line | {"time": ""} == {"time": "", "level": "WARNING", "request_id": "r1", "logger": "app.x",
                                   "message": "draft failed with code"}
