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


def test_a_mismatched_agent_token_is_rejected_even_on_readyz(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_TOKEN", "correct-token")
    email_agent.get_settings.cache_clear()
    client = TestClient(email_agent.app, client=("203.0.113.9", 50000))
    # Correct token passes
    assert client.get("/readyz", headers={"X-AIMail-Agent-Token": "correct-token"}).status_code == 200
    # Mismatched token returns 403
    assert client.get("/readyz", headers={"X-AIMail-Agent-Token": "wrong-token"}).status_code == 403



def test_a_json_log_line_carries_the_same_fields_as_text():
    record = logging.LogRecord("app.x", logging.WARNING, __file__, 1, "draft failed with %s", ("code",), None)
    record.request_id = "r1"
    line = json.loads(JsonFormatter().format(record))
    assert line | {"time": ""} == {"time": "", "level": "WARNING", "request_id": "r1", "logger": "app.x",
                                   "message": "draft failed with code"}


def test_an_unreachable_presidio_is_a_failed_check_and_a_reachable_one_passes(monkeypatch, test_settings):
    real_client = health.httpx.AsyncClient

    def answering(status):
        transport = health.httpx.MockTransport(lambda request: health.httpx.Response(status, json=[]))
        monkeypatch.setattr(health.httpx, "AsyncClient", lambda **kw: real_client(transport=transport))

    answering(200)
    assert asyncio.run(health.presidio_answers()) is True
    answering(401)  # a wrong password on a tunnel is as broken as no Presidio
    assert asyncio.run(health.presidio_answers()) is False


def test_the_backend_reports_presidio_beside_the_database(api_client, monkeypatch):
    def broken_engine():
        raise OSError("connection refused")

    real_client = health.httpx.AsyncClient
    transport = health.httpx.MockTransport(lambda request: health.httpx.Response(200, json=[]))
    monkeypatch.setattr(health.httpx, "AsyncClient", lambda **kw: real_client(transport=transport))
    monkeypatch.setattr(health, "get_engine", broken_engine)
    body = api_client.get("/readyz").json()
    assert body["checks"] == {"database": "failed", "presidio": "ok"}
