"""Private mode (specs/features/local-model.md): the user's email never reaches Gemini."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

import email_agent
import gemini_client
from app import dashboard, private_mode_routes
from app.core.config import get_settings
from app.core.constants import LOCAL_EMBEDDING_DIM
from app.core.ownership import EVERYTHING
from app.private_mode import DraftProvider
from app.rag import ingest
from app.rag import retrieve as retrieve_module
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


def test_a_private_draft_searches_locally_and_asks_for_the_local_model(mailbox, monkeypatch):  # noqa: F811
    searched = []

    async def retrieve(_email, k, *, scope, provider):
        searched.append(provider)
        return []

    async def local(_user_id):
        return DraftProvider.LOCAL

    monkeypatch.setattr(dashboard, "retrieve", retrieve)
    monkeypatch.setattr(dashboard, "provider_for", local)
    asyncio.run(dashboard.regenerate_email(str(mailbox["message"].id), scope=EVERYTHING))
    payload = json.loads(mailbox["payloads"][0])
    assert payload["provider"] == "local" and searched == [DraftProvider.LOCAL]


@pytest.fixture
def no_gemini_embedding(monkeypatch):
    async def gemini(*_args, **_kwargs):
        raise AssertionError("a Private mode search reached the Gemini embedding call")

    monkeypatch.setattr(retrieve_module, "embed_query", gemini)


def test_a_private_search_without_a_local_embedding_model_finds_nothing(test_settings, no_gemini_embedding):
    found = asyncio.run(retrieve_module.retrieve("Is Thursday still on?", 5, scope=EVERYTHING,
                                                 provider=DraftProvider.LOCAL))
    assert found == []


def test_a_private_search_embeds_and_searches_only_locally(test_settings, no_gemini_embedding, monkeypatch):
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "embeddinggemma")
    get_settings.cache_clear()
    embedded = []

    async def local(text):
        embedded.append(text)
        return [0.0] * LOCAL_EMBEDDING_DIM

    monkeypatch.setattr(retrieve_module, "embed_query_locally", local)
    statement = asyncio.run(retrieve_module._local_search("Is Thursday still on?", 5, EVERYTHING))
    sql = str(statement)
    assert embedded == ["Is Thursday still on?"]
    assert "local_embedding" in sql and "JOIN embedding " not in sql


def test_the_gemini_embedding_pass_leaves_out_private_mode_users_chunks():
    sql = str(ingest._pending_for_gemini(10).compile(compile_kwargs={"literal_binds": True}))
    assert "user_preferences.draft_provider = 'local'" in sql and "NOT IN" in sql


def test_two_embedding_passes_never_take_the_same_chunk(test_settings):
    for pending in (ingest._pending_for_gemini, ingest._pending_for_local):
        sql = str(pending(10).compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE OF chunk SKIP LOCKED" in sql


def test_private_mode_cannot_be_switched_on_where_the_company_has_not_set_it_up(calls, monkeypatch):  # noqa: F811
    monkeypatch.setattr(private_mode_routes, "is_offered", lambda: False)
    response = _signed_in().put("/settings/private-mode", json={"enabled": True}, headers=CLIENT)
    assert response.status_code == 409 and response.json()["error"]["code"] == "private_mode_unavailable"


def test_private_mode_can_always_be_switched_off_even_where_it_is_no_longer_set_up(calls, monkeypatch):  # noqa: F811
    saved = []

    async def save(user_id, provider):
        saved.append(provider)

    async def still_local(_user_id):
        return DraftProvider.GEMINI if saved else DraftProvider.LOCAL

    async def nothing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(private_mode_routes, "is_offered", lambda: False)
    monkeypatch.setattr(private_mode_routes, "audit", nothing)
    monkeypatch.setattr(private_mode_routes, "_save_choice", save)
    monkeypatch.setattr(private_mode_routes, "provider_for", still_local)
    response = _signed_in().put("/settings/private-mode", json={"enabled": False}, headers=CLIENT)
    assert response.status_code == 200 and saved == [DraftProvider.GEMINI]
    assert response.json() == {"available": False, "enabled": False, "model": "", "search": False}


@pytest.mark.parametrize(("model", "is_searched"), [("embeddinggemma", True), ("", False)])
def test_the_card_says_whether_private_drafts_search_documents(calls, monkeypatch, model, is_searched):  # noqa: F811
    async def local(_user_id):
        return DraftProvider.LOCAL

    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", model)
    get_settings.cache_clear()
    monkeypatch.setattr(private_mode_routes, "provider_for", local)
    assert _signed_in().get("/settings/private-mode").json()["search"] is is_searched
