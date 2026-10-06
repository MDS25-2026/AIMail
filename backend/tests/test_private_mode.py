"""Private mode (specs/features/local-model.md): the user's email never reaches Gemini."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import email_agent
import gemini_client
from app import dashboard, private_mode_routes
from app.core.ownership import EVERYTHING
from app.private_mode import DraftProvider
from gemini_client import GeminiError, GeminiErrorCode
from tests.test_account import _signed_in, calls  # noqa: F401  (fixture)
from tests.test_restorable_masking import mailbox  # noqa: F401  (fixture)

CLIENT = {"X-AIMail-Client": "1"}
_FILLERS = {"string": "ok", "number": 0.95, "integer": 0, "boolean": True, "array": []}


def _answer_from(schema: dict) -> dict:
    """A well-formed answer to any schema the agent asks for."""
    return {name: (prop.get("enum") or [_FILLERS[prop["type"]]])[0]
            for name, prop in schema["properties"].items()}


@pytest.fixture
def local_only(monkeypatch):
    asked = []

    async def gemini(*_args, **_kwargs):
        raise AssertionError("a Private mode request reached Gemini")

    async def local(prompt, response_schema=None, max_output_tokens=None):
        asked.append(prompt)
        return _answer_from(response_schema) if response_schema else "Hi [PERSON_1], noted. [PERSON_9]"

    monkeypatch.setattr(email_agent, "generate", gemini)
    # Also where a request actually leaves, so a stage calling the client directly is caught too.
    monkeypatch.setattr(gemini_client, "call_model", gemini)
    monkeypatch.setattr(email_agent, "generate_local", local)
    return asked


def test_a_private_draft_refine_and_translation_never_reach_gemini(local_only):
    agent = TestClient(email_agent.app)
    draft = agent.post("/process-email", json={
        "thread_context": "", "email_body": "Hi, I'm [PERSON_1]. Is Thursday still on?",
        "rag_context": "", "sign_off": "[PERSON_9]", "provider": "local"})
    refine = agent.post("/refine", json={
        "email_body": "Is Thursday still on?", "draft": "Yes.", "instruction": "warmer", "provider": "local"})
    translate = agent.post("/translate", json={"text": "Is Thursday still on?", "language": "ms", "provider": "local"})
    assert (draft.status_code, refine.status_code) == (200, 200)
    assert translate.status_code in (200, 422)  # 422: the stub's text fails the faithfulness check
    assert len(local_only) >= 5  # router, summary, actions, draft, critic, refine, translation


def test_without_the_local_model_a_private_draft_fails_and_does_not_fall_back(monkeypatch):
    async def gemini(*_args, **_kwargs):
        raise AssertionError("fell back to Gemini")

    async def down(*_args, **_kwargs):
        raise GeminiError(GeminiErrorCode.UNAVAILABLE, "ollama not running")

    monkeypatch.setattr(email_agent, "generate", gemini)
    monkeypatch.setattr(email_agent, "generate_local", down)
    response = TestClient(email_agent.app).post("/process-email", json={
        "thread_context": "", "email_body": "Hi", "rag_context": "", "provider": "local"})
    assert response.status_code == 503


def test_a_private_draft_skips_retrieval_and_asks_for_the_local_model(mailbox, monkeypatch):  # noqa: F811
    async def no_retrieval(*_args, **_kwargs):
        raise AssertionError("retrieval embeds the email with Gemini")

    async def local(_user_id):
        return DraftProvider.LOCAL

    monkeypatch.setattr(dashboard, "retrieve", no_retrieval)
    monkeypatch.setattr(dashboard, "provider_for", local)
    asyncio.run(dashboard.regenerate_email(str(mailbox["message"].id), scope=EVERYTHING))
    payload = json.loads(mailbox["payloads"][0])
    assert payload["provider"] == "local" and payload["rag_context"] == ""


def test_private_mode_cannot_be_switched_on_where_the_company_has_not_set_it_up(calls, monkeypatch):  # noqa: F811
    monkeypatch.setattr(private_mode_routes, "is_offered", lambda: False)
    response = _signed_in().put("/settings/private-mode", json={"enabled": True}, headers=CLIENT)
    assert response.status_code == 409 and response.json()["detail"] == "private_mode_unavailable"


def test_private_mode_can_always_be_switched_off_even_where_it_is_no_longer_set_up(calls, monkeypatch):  # noqa: F811
    saved = []

    async def save(user_id, provider):
        saved.append(provider)

    async def still_local(_user_id):
        return DraftProvider.GEMINI if saved else DraftProvider.LOCAL

    monkeypatch.setattr(private_mode_routes, "is_offered", lambda: False)
    monkeypatch.setattr(private_mode_routes, "_save_choice", save)
    monkeypatch.setattr(private_mode_routes, "provider_for", still_local)
    response = _signed_in().put("/settings/private-mode", json={"enabled": False}, headers=CLIENT)
    assert response.status_code == 200 and saved == [DraftProvider.GEMINI]
    assert response.json() == {"available": False, "enabled": False, "model": ""}
