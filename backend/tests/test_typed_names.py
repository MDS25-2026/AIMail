"""Names a person types are hidden from the model and put back after (specs/features/privacy-gaps.md)."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app import dashboard
from app.core import typed_names
from app.core.config import get_settings
from app.core.ownership import EVERYTHING
from app.core.typed_names import TypedNames
from app.rag import mask
from app.rag.mask import DocumentMaskingError
from tests.test_restorable_masking import _Session, mailbox  # noqa: F401  (the fixture)

NEW_NAME = "Tan Mei Ling"


def _finds(monkeypatch, *names):
    async def found(text):
        return [name for name in names if name in text]

    monkeypatch.setattr(typed_names, "find_people", found)


def _presidio_down(monkeypatch):
    async def down(_text):
        raise DocumentMaskingError("presidio down")

    monkeypatch.setattr(typed_names, "find_people", down)


def test_a_typed_name_becomes_a_placeholder_and_comes_back(monkeypatch):
    _finds(monkeypatch, NEW_NAME)
    names = TypedNames()
    hidden = asyncio.run(names.hide(f"Please cc {NEW_NAME}."))
    assert hidden == "Please cc [PERSON_800]."
    assert names.restore("Copied [PERSON_800] as asked.") == f"Copied {NEW_NAME} as asked."


def test_the_same_name_keeps_one_number_across_texts_and_cases(monkeypatch):
    _finds(monkeypatch, "Mei Ling", "mei ling", "Ahmad")
    names = TypedNames()
    first = asyncio.run(names.hide("Ask Mei Ling."))
    second = asyncio.run(names.hide("Tell mei ling and Ahmad."))
    assert (first, second) == ("Ask [PERSON_800].", "Tell [PERSON_800] and [PERSON_801].")


def test_a_longer_name_is_hidden_whole_before_a_shorter_one_inside_it(monkeypatch):
    _finds(monkeypatch, "Aisyah binti Ali", "Ali")
    hidden = asyncio.run(TypedNames().hide("Aisyah binti Ali met Ali."))
    assert hidden == "[PERSON_800] met [PERSON_801]."


def test_a_malay_name_found_only_from_binti_is_hidden_with_its_given_name(monkeypatch):
    _finds(monkeypatch, "binti Ali")
    assert asyncio.run(TypedNames().hide("Tell Siti Aisyah binti Ali today.")) == "Tell [PERSON_800] today."


def test_names_in_every_string_of_an_agent_answer_are_restored(monkeypatch):
    _finds(monkeypatch, NEW_NAME)
    names = TypedNames()
    asyncio.run(names.hide(NEW_NAME))
    answer = {"draft": "Hi [PERSON_800]", "confidence": 0.9,
              "review_codes": [{"code": "unaddressed", "items": ["[PERSON_800]'s date"]}]}
    assert names.restore_answer(answer) == {"draft": f"Hi {NEW_NAME}", "confidence": 0.9,
                                            "review_codes": [{"code": "unaddressed", "items": [f"{NEW_NAME}'s date"]}]}


def test_the_analyzer_never_hides_part_of_a_placeholder(monkeypatch, test_settings):
    def analyzer(request: httpx.Request) -> httpx.Response:
        text = json.loads(request.read())["text"]
        start = text.find("PERSON_1")
        return httpx.Response(200, json=[{"entity_type": "PERSON", "start": start, "end": start + 8, "score": 0.9}])

    real_client = httpx.AsyncClient
    monkeypatch.setattr(mask.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(analyzer)))
    assert asyncio.run(mask.find_people("Thanks [PERSON_1].")) == []


def test_a_refine_sends_a_new_typed_name_as_a_placeholder_and_stores_it_back(mailbox, monkeypatch):  # noqa: F811
    _finds(monkeypatch, NEW_NAME)

    async def call_agent(path, request, _answer=None):
        mailbox["payloads"].append(json.dumps(request.model_dump(mode="json")))
        return {"draft": "Dear [PERSON_1], I have copied [PERSON_800].", "confidence": 0.95}

    monkeypatch.setattr(dashboard, "_call_agent", call_agent)
    message = mailbox["message"]
    asyncio.run(dashboard.refine_email(str(message.id), f"Say you copied {NEW_NAME}", "Dear [PERSON_1],",
                                       scope=EVERYTHING))
    assert NEW_NAME not in mailbox["payloads"][0] and "[PERSON_800]" in mailbox["payloads"][0]
    assert message.draft_reply == f"Dear [PERSON_1], I have copied {NEW_NAME}."


def test_a_name_put_back_into_stored_action_items_is_hidden_again_on_the_next_refine(mailbox, monkeypatch):  # noqa: F811
    _finds(monkeypatch, NEW_NAME)
    mailbox["message"].action_items = [f"Call {NEW_NAME} back"]
    asyncio.run(dashboard.refine_email(str(mailbox["message"].id), "Shorter", "Dear [PERSON_1],", scope=EVERYTHING))
    payload = json.loads(mailbox["payloads"][0])
    assert NEW_NAME not in mailbox["payloads"][0] and payload["action_items"] == ["Call [PERSON_800] back"]


def test_a_template_variable_is_never_touched_by_the_name_check(monkeypatch):
    _finds(monkeypatch, "Customer Name", NEW_NAME)
    sent = []

    async def call_agent(path, request, _answer=None):
        sent.append(request.text)
        return {"language": "ms", "text": request.text.replace("Dear", "Kepada"), "egress": []}

    async def nothing(*_args, **_kwargs):
        return None

    async def gemini(_user_id):
        return "gemini"

    monkeypatch.setattr(dashboard, "_call_agent", call_agent)
    monkeypatch.setattr(dashboard, "save_egress", nothing)
    monkeypatch.setattr(dashboard, "model_for", gemini)
    template = SimpleNamespace(body=f"Dear {{{{Customer Name}}}}, {NEW_NAME} will call.", user_id=None, language="en")
    translated = asyncio.run(dashboard.translate_template(template, dashboard.Language.MS))
    assert NEW_NAME not in sent[0] and "Customer Name" not in sent[0]
    assert translated == f"Kepada {{{{Customer Name}}}}, {NEW_NAME} will call."


def test_a_reply_refined_with_a_new_name_still_sends_with_that_name(mailbox, monkeypatch):  # noqa: F811
    message = mailbox["message"]
    monkeypatch.setattr(dashboard, "get_sessionmaker", lambda: lambda: _Session(message))
    asyncio.run(dashboard.approve_and_send(str(message.id), f"Dear [PERSON_1], I have copied {NEW_NAME}.",
                                           scope=EVERYTHING))
    assert mailbox["sent"] == [f"Dear Aisyah Rahman, I have copied {NEW_NAME}."]


def test_a_refine_is_refused_rather_than_sending_names_when_presidio_is_down(mailbox, monkeypatch):  # noqa: F811
    _presidio_down(monkeypatch)
    with pytest.raises(DocumentMaskingError):
        asyncio.run(dashboard.refine_email(str(mailbox["message"].id), f"Copy {NEW_NAME}", "Dear [PERSON_1],",
                                           scope=EVERYTHING))
    assert mailbox["payloads"] == []


def test_a_tunnelled_presidio_gets_basic_auth_and_a_local_one_none(monkeypatch, test_settings):
    sent = []

    def analyzer(request: httpx.Request) -> httpx.Response:
        sent.append(request.headers.get("authorization"))
        return httpx.Response(200, json=[])

    real_client = httpx.AsyncClient
    monkeypatch.setattr(mask.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(analyzer), auth=kw.get("auth")))
    asyncio.run(mask.find_people("Hello"))
    monkeypatch.setenv("PRESIDIO_USER", "aimail")
    monkeypatch.setenv("PRESIDIO_PASSWORD", "not-a-real-password")
    get_settings.cache_clear()
    asyncio.run(mask.find_people("Hello"))
    assert sent[0] is None and sent[1].startswith("Basic ")
