"""A "Subject:" line the model writes into a draft is removed where the draft is made."""

import pytest

import gemini_client
import model_gateway
from app.core.draft_text import strip_subject_line
from tests.conftest import agent_client
from tests.test_private_mode import _answer_from


@pytest.mark.parametrize(("draft", "expected"), [
    ("Subject: Re: Invoice\n\nHi, paid.", "Hi, paid."),
    ("  subject : Re: x\r\n\r\nHi", "Hi"),
    ("Hi, the subject: is fine here.", "Hi, the subject: is fine here."),
])
def test_only_a_leading_subject_line_is_dropped(draft, expected):
    assert strip_subject_line(draft) == expected


@pytest.fixture
def model_writes_a_subject_line(monkeypatch):
    async def local(prompt, response_schema=None, max_output_tokens=None, system=None):
        return _answer_from(response_schema) if response_schema else "Subject: Re: Thursday\n\nHi [PERSON_1], noted."

    async def gemini(*_args, **_kwargs):
        raise AssertionError("unexpected Gemini call")

    monkeypatch.setattr(model_gateway, "gemini_generate", gemini)
    monkeypatch.setattr(gemini_client, "call_model", gemini)
    monkeypatch.setattr(model_gateway, "generate_local", local)


def test_a_generated_draft_comes_back_without_the_subject_line(model_writes_a_subject_line):
    response = agent_client().post("/process-email", json={
        "thread_context": "", "email_body": "Hi, I'm [PERSON_1]. Is Thursday still on?",
        "rag_context": "", "sign_off": "[PERSON_9]", "provider": "local"})
    assert response.status_code == 200
    assert response.json()["draft"].startswith("Hi [PERSON_1]")


def test_a_refined_draft_comes_back_without_the_subject_line(model_writes_a_subject_line):
    response = agent_client().post("/refine", json={
        "email_body": "Is Thursday still on?", "draft": "Yes.", "instruction": "warmer", "provider": "local"})
    assert response.status_code == 200
    assert not response.json()["draft"].lower().startswith("subject")
