"""The drafting loop: failed checks drive the repair, and the best checked draft survives a failure.

The PII scan and the figures check used to run once, after the loop, so a leaking draft was never
rewritten; the repair saw only the critic's dict as text; and a failed critique threw the draft away.
"""

import pytest
from pydantic import ValidationError

import email_agent
from model_runtime import ModelError, ModelErrorCode
from tests.conftest import agent_client
from tests.drafting import GOOD_VERDICT, candidate

EMAIL = {"thread_context": "", "email_body": "Can you confirm the refund?",
         "rag_context": "Refunds are paid within 14 days.", "provider": "gemini"}


@pytest.fixture
def agent(monkeypatch):
    """Drafts come from `drafts` in order; the critic and the scanner answer per draft."""
    state = {"drafts": ["First draft."], "verdicts": {}, "pii": {}, "repair_prompts": [],
             "repair_error": None, "critic_error": None}

    async def gemini(prompt, response_schema=None, max_output_tokens=None, *, purpose):
        if purpose == email_agent.Stage.ROUTE:
            return {"category": "STANDARD"}
        if purpose == email_agent.Stage.ACTIONS:
            return {"action_items": []}
        if state["critic_error"]:
            raise ModelError(state["critic_error"], "test")
        draft = prompt.split("<draft_reply>\n", 1)[1].split("\n</draft_reply>", 1)[0]
        return state["verdicts"].get(draft, GOOD_VERDICT)

    async def llm(_system, user_prompt, max_tokens=0, *, purpose):
        if purpose == email_agent.Stage.SUMMARY:
            return "A refund question."
        if purpose == email_agent.Stage.REPAIR:
            state["repair_prompts"].append(user_prompt)
            if state["repair_error"]:
                raise ModelError(state["repair_error"], "test")
        return state["drafts"].pop(0)

    async def scan(draft):
        return state["pii"].get(draft, [])

    monkeypatch.setattr(email_agent, "call_gemini", gemini)
    monkeypatch.setattr(email_agent, "call_llm", llm)
    monkeypatch.setattr(email_agent, "scan_draft_pii", scan)
    return state


def _draft() -> dict:
    response = agent_client().post("/process-email", json=EMAIL)
    assert response.status_code == 200
    return response.json()


def test_a_leak_is_repaired_even_when_the_critic_is_confident(agent):
    agent["drafts"] = ["Call me on 012-3456789.", "I will confirm the refund."]
    agent["pii"] = {"Call me on 012-3456789.": ["MY_PHONE"]}
    body = _draft()
    assert body["draft"] == "I will confirm the refund." and body["attempts"] == 1
    assert "remove the MY_PHONE" in agent["repair_prompts"][0]


def test_the_repair_is_told_which_figure_to_fix(agent):
    agent["drafts"] = ["It will be paid within 60 days.", "It will be paid within 14 days."]
    body = _draft()
    assert "the figure 60" in agent["repair_prompts"][0]
    assert body["unsupported_specifics"] == []


def test_an_unreachable_scanner_is_flagged_but_not_repaired(agent):
    agent["pii"] = {"First draft.": ["PRESIDIO_UNAVAILABLE"]}
    body = _draft()
    assert body["attempts"] == 0 and body["pii_clean"] is None and body["needs_human_review"] is True


def test_a_worse_rewrite_does_not_replace_a_better_draft(agent):
    agent["drafts"] = ["First draft.", "Call me on 012-3456789.", "Still 012-3456789.", "Again 012-3456789."]
    agent["verdicts"] = {"First draft.": GOOD_VERDICT | {"confidence": 0.5}}
    agent["pii"] = {draft: ["MY_PHONE"] for draft in agent["drafts"][1:]}
    body = _draft()
    assert body["draft"] == "First draft." and body["pii_findings"] == [] and body["attempts"] == 3


def test_a_failed_repair_returns_the_draft_it_had_with_that_drafts_checks(agent):
    agent["drafts"] = ["It will be paid within 60 days."]
    agent["repair_error"] = ModelErrorCode.DEADLINE_EXCEEDED
    body = _draft()
    assert body["draft"] == "It will be paid within 60 days." and body["unsupported_specifics"] == ["60"]
    assert body["attempts"] == 0 and f"repair stopped: {ModelErrorCode.DEADLINE_EXCEEDED}" in body["review_reasons"]


def test_a_failed_critique_keeps_the_draft_and_says_why(agent):
    agent["critic_error"] = ModelErrorCode.MALFORMED_JSON
    body = _draft()
    assert body["draft"] == "First draft." and body["confidence"] is None and body["attempts"] == 0
    assert f"critic unavailable: {ModelErrorCode.MALFORMED_JSON}" in body["review_reasons"]


def test_a_refine_whose_critique_fails_keeps_the_users_revision(agent):
    agent["drafts"] = ["Friday is fine."]
    agent["critic_error"] = ModelErrorCode.UNAVAILABLE
    response = agent_client().post("/refine", json={"email_body": "Friday?", "draft": "Friday works.",
                                                    "instruction": "shorter", "provider": "gemini"})
    assert response.status_code == 200 and response.json()["draft"] == "Friday is fine."
    assert response.json()["needs_human_review"] is True


def test_every_draft_records_the_prompt_version(agent):
    assert _draft()["prompt_version"] == email_agent.PROMPT_VERSION


@pytest.mark.parametrize("field, value", [
    ("unaddressed_items", ["2"]), ("unaddressed_items", [None]), ("unaddressed_items", [True]),
    ("grounding_ok", "true"), ("issues", [3]), ("completeness", None),
])
def test_a_critic_verdict_with_a_wrong_type_is_refused_whole(field, value):
    with pytest.raises(ValidationError):
        email_agent.CriticVerdict.model_validate(GOOD_VERDICT | {field: value})


def test_a_draft_that_fails_a_check_ranks_below_one_that_passes_with_less_confidence():
    leaking = candidate(pii=["MY_PHONE"], confidence=0.99)
    clean = candidate(confidence=0.6)
    assert clean.rank() > leaking.rank()
