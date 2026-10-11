"""A prompt that reached a model is on the privacy receipt even when the call failed (privacy-gaps.md)."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx

import model_gateway
from app import agent_client, dashboard
from model_runtime import ModelError, ModelErrorCode
from tests.conftest import agent_client as agent_app

RECORD = {"purpose": "draft", "provider": "gemini", "chars": 10, "sha256": "x", "hidden": {}, "caught": 0}


def _refused(body) -> httpx.Response:
    return httpx.Response(503, json=body, request=httpx.Request("POST", "http://agent/process-email"))


def test_the_agent_returns_what_it_sent_before_a_model_failure(monkeypatch):
    async def down(*_args, **_kwargs):
        raise ModelError(ModelErrorCode.UNAVAILABLE, "test")

    monkeypatch.setattr(model_gateway, "gemini_generate", down)
    response = agent_app().post("/process-email", json={
        "thread_context": "", "email_body": "Can you confirm the refund?", "rag_context": "", "provider": "gemini"})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == ModelErrorCode.UNAVAILABLE and detail["egress"]
    assert all("Can you confirm" not in str(record) for record in detail["egress"])  # no prompt text


def test_only_the_agents_own_refusal_shape_is_read_for_records():
    assert agent_client.refusal_egress(_refused({"detail": {"code": "x", "egress": [RECORD]}})) == [RECORD]
    assert agent_client.refusal_egress(_refused({"detail": [{"loc": ["body"], "msg": "bad"}]})) == []
    assert agent_client.refusal_egress(_refused({"detail": "gemini_unavailable"})) == []
    assert agent_client.refusal_egress(_refused(["not", "a", "dict"])) == []


def test_a_failed_draft_keeps_the_search_and_the_agents_records(monkeypatch):
    saved = []
    message = SimpleNamespace(id=uuid4(), user_id=uuid4(), body_masked="Refund?", thread_id=None,
                              received_at=None)

    async def searched(*_args, **_kwargs):
        model_gateway._egress.get().append(model_gateway.Egress(**RECORD | {"purpose": "search"}))
        return []

    async def refused(*_args, **_kwargs):
        raise httpx.HTTPStatusError("down", request=httpx.Request("POST", "http://agent"),
                                    response=_refused({"detail": {"code": "gemini_unavailable", "egress": [RECORD]}}))

    async def save(records, **_kwargs):
        saved.extend(records)

    async def gemini(_user_id):
        return "gemini"

    async def no_style(_message):
        return {}

    for name, value in (("retrieve", searched), ("_call_agent", refused), ("save_egress", save),
                        ("provider_for", gemini), ("_style_fields", no_style)):
        monkeypatch.setattr(dashboard, name, value)
    result = asyncio.run(dashboard._generate(message, dashboard.Tone.PROFESSIONAL, [],
                                             dashboard.ThreadMap()))
    assert result == {}
    assert [record["purpose"] for record in saved] == ["search", "draft"]
