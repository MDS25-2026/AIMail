"""Names a person types are hidden from the model and put back after (specs/features/privacy-gaps.md)."""

import asyncio
import json

import httpx
import pytest

from app import dashboard
from app.core import typed_names
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
