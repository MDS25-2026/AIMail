"""Saved reply templates (specs/features/reply-templates.md)."""

import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import dashboard, template_routes, template_store
from app.core import auth
from app.core.errors import DomainError, ErrorCode
from app.core.language import Language
from app.core.ownership import EVERYTHING
from app.core.vault import ThreadMap
from app.templates import (
    fill_variables,
    format_day,
    has_unfilled_variable,
    matching_template_id,
    protect_variables,
    restore_variables,
)
from tests.test_account import ALICE, _signed_in, calls  # noqa: F401  (fixture)

CLIENT = {"X-AIMail-Client": "1"}


def test_the_variables_aimail_knows_are_filled_and_the_rest_are_left_as_written():
    body = "Hi {{name}},\nYour invoice {{invoice number}} is attached.\n{{ My  Name }}, {{today}}"
    filled = fill_variables(body, sender="[PERSON_3]", owner="[PERSON_2]", today="10 October 2026")
    assert filled == "Hi [PERSON_3],\nYour invoice {{invoice number}} is attached.\n[PERSON_2], 10 October 2026"


def test_malay_and_chinese_variable_names_are_filled_too():
    filled = fill_variables("Salam {{nama}}, {{hari ini}}. 您好{{名字}}", sender="[PERSON_1]", owner=None, today="X")
    assert filled == "Salam [PERSON_1], X. 您好[PERSON_1]"


def test_a_name_aimail_does_not_know_stays_a_blank():
    assert fill_variables("Hi {{name}}", sender=None, owner=None, today="X") == "Hi {{name}}"


@pytest.mark.parametrize(("language", "expected"), [
    (Language.EN, "10 October 2026"), (Language.MS, "10 Oktober 2026"), (Language.ZH, "2026年10月10日"),
])
def test_today_is_written_in_the_templates_language(language, expected):
    assert format_day(date(2026, 10, 10), language) == expected


def test_a_leftover_blank_is_detected_and_a_filled_draft_is_not():
    assert has_unfilled_variable("Join at {{meeting link}}")
    assert not has_unfilled_variable("Join at https://meet.example/abc")


def test_the_suggestion_needs_the_same_language_and_a_trigger_word():
    templates = [("t1", "ms", ["invois"]), ("t2", "en", ["invoice"]), ("t3", "en", ["INVOICE"])]
    assert matching_template_id(templates, Language.EN, "Please resend the Invoice") == "t2"
    assert matching_template_id(templates, Language.EN, "Lunch on Friday?") is None
    assert matching_template_id([("t1", "zh", ["发票"])], Language.ZH, "请把发票再发一次") == "t1"


def test_translation_keeps_every_variable_or_is_refused():
    protected, variables = protect_variables("Hi {{name}}, link: {{meeting link}}")
    assert protected == "Hi [VAR_1], link: [VAR_2]" and len(variables) == 2
    assert restore_variables("Hai [VAR_1], pautan: [VAR_2]", variables) == "Hai {{name}}, pautan: {{meeting link}}"
    assert restore_variables("Hai [VAR_1], pautan: tiada", variables) is None


def test_a_newer_message_naming_someone_new_never_moves_the_owner_or_the_sender():
    """A stored draft signed [PERSON_900] still reads the owner's name after the thread grows."""
    def thread(*messages: tuple[str, dict[str, str], str]) -> ThreadMap:
        built = ThreadMap()
        for key, values, text in messages:
            built.add_message(key, values, text)
        built.add_owner("Ely Tan")
        built.add_sender("Aisyah Rahman")
        return built

    first = ("m1", {"[PERSON_1]": "Aisyah"}, "Hi I'm [PERSON_1]")
    later = ("m2", {"[PERSON_1]": "Ben Lim"}, "Hello, [PERSON_1] here")
    draft = "Hi [PERSON_901], about [PERSON_1]. Regards, [PERSON_900]"
    expected = "Hi Aisyah Rahman, about Aisyah. Regards, Ely Tan"
    assert thread(first).restore(draft)[0] == expected
    assert thread(first, later).restore(draft)[0] == expected


def test_a_draft_with_a_template_blank_cannot_be_sent():
    with pytest.raises(dashboard.SendRejectedError) as refused:
        dashboard._outgoing("Hi, join at {{meeting link}}", ThreadMap())
    assert refused.value.code == ErrorCode.UNRESOLVED_PLACEHOLDERS


def _template(**fields) -> SimpleNamespace:
    defaults = {"id": uuid4(), "user_id": ALICE, "title": "Invoice", "body": "Hi {{name}}", "language": "en",
                "trigger_keywords": ["invoice"], "last_used_at": None}
    return SimpleNamespace(**(defaults | fields))


@pytest.fixture
def store(monkeypatch):
    """The template store in memory, plus a record of what was audited and marked used."""
    state = {"templates": {}, "used": [], "audits": []}

    async def list_all(user_id):
        return [t for t in state["templates"].values() if t.user_id == user_id]

    async def get(user_id, template_id):
        template = state["templates"].get(template_id)
        return template if template and template.user_id == user_id else None

    async def create(user_id, fields):
        template = _template(user_id=user_id, **fields)
        state["templates"][template.id] = template
        return template

    async def used(template_id):
        state["used"].append(template_id)

    async def audit(action, **fields):
        state["audits"].append(action)

    async def own_mailbox(_principal):
        return EVERYTHING

    for name, value in (("list_templates", list_all), ("get_template", get), ("create_template", create),
                        ("mark_used", used), ("audit", audit)):
        monkeypatch.setattr(template_routes, name, value)
    monkeypatch.setattr(auth, "scope_of_principal", own_mailbox)
    return state


def test_a_template_is_saved_and_listed_for_its_owner(calls, store):  # noqa: F811
    client = _signed_in()
    created = client.post("/templates", json={"title": "Invoice", "body": "Hi {{name}}", "language": "en",
                                              "triggerKeywords": [" invoice "]}, headers=CLIENT)
    assert created.status_code == 201 and created.json()["triggerKeywords"] == ["invoice"]
    assert [t["title"] for t in client.get("/templates").json()] == ["Invoice"]


def test_someone_elses_template_answers_like_a_missing_one(calls, store):  # noqa: F811
    theirs = _template(user_id=uuid4())
    store["templates"][theirs.id] = theirs
    response = _signed_in().post(f"/templates/{theirs.id}/fill", json={"emailId": str(uuid4())}, headers=CLIENT)
    assert response.status_code == 404


def test_a_template_over_the_limits_is_refused(calls, store):  # noqa: F811
    response = _signed_in().post("/templates", json={"title": "x", "body": "y", "language": "en",
                                                     "triggerKeywords": ["k"] * 11}, headers=CLIENT)
    assert response.status_code == 422


def test_inserting_fills_the_template_and_marks_it_used(calls, store, monkeypatch):  # noqa: F811
    mine = _template()
    store["templates"][mine.id] = mine

    async def fill(_email_id, template, *, scope):
        return template.body.replace("{{name}}", "[PERSON_3]")

    monkeypatch.setattr(template_routes, "fill_template", fill)
    response = _signed_in().post(f"/templates/{mine.id}/fill", json={"emailId": str(uuid4())}, headers=CLIENT)
    assert response.json() == {"text": "Hi [PERSON_3]"}
    assert store["used"] == [mine.id] and store["audits"] == ["template_used"]


def test_the_fiftyfirst_template_is_refused(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            return self

        async def scalar(self, _statement):
            return 50

    monkeypatch.setattr(template_store, "get_sessionmaker", lambda: Session)
    with pytest.raises(DomainError) as refused:
        asyncio.run(template_store.create_template(ALICE, {"title": "x"}))
    assert refused.value.code == ErrorCode.TOO_MANY_TEMPLATES


def test_a_translated_template_that_lost_a_variable_is_refused(monkeypatch):
    async def call_agent(_path, request, _answer):
        assert "{{" not in request.text  # the variables travel as markers
        return {"text": "Hai, sila datang.", "egress": []}

    async def nothing(*_args, **_kwargs):
        return None

    async def gemini(_user_id):
        return "gemini"

    monkeypatch.setattr(dashboard, "_call_agent", call_agent)
    monkeypatch.setattr(dashboard, "save_egress", nothing)
    monkeypatch.setattr(dashboard, "provider_for", gemini)
    with pytest.raises(dashboard.TranslationError) as refused:
        asyncio.run(dashboard.translate_template(_template(body="Hi {{name}}, please come."), Language.MS))
    assert refused.value.code == ErrorCode.TRANSLATION_UNFAITHFUL


def test_the_suggestion_reads_the_owners_templates_most_recent_first(monkeypatch):
    async def listed(_user_id):
        return [_template(id="recent", trigger_keywords=["invoice"]), _template(id="older")]

    monkeypatch.setattr(template_store, "list_templates", listed)
    assert asyncio.run(template_store.suggested_template_id(ALICE, "About the invoice")) == "recent"
    assert asyncio.run(template_store.suggested_template_id(None, "About the invoice")) is None
