"""The agent treats restorable placeholders as the details they stand for."""

import asyncio

import email_agent
from tests.drafting import GOOD_VERDICT, context


def test_a_placeholder_number_is_not_reported_as_an_invented_figure():
    assert email_agent.unsupported_specifics("Dear [PERSON_2], we will ring [PHONE_12].", "Hi [PHONE_12]") == []
    assert email_agent.unsupported_specifics("Dear [PERSON_12], it costs RM 850.", "Hi") == ["850"]


def test_the_critic_is_told_a_placeholder_is_not_a_gap_or_a_leak(monkeypatch):
    prompts = []

    async def capture(prompt, **_kwargs):
        prompts.append(prompt)
        return GOOD_VERDICT

    monkeypatch.setattr(email_agent, "call_gemini", capture)
    asyncio.run(email_agent.evaluate_reply(context(email_body="Hi [PERSON_1]"), "Dear [PERSON_1]"))
    assert "[PERSON_1] is filled in with the real detail" in prompts[0]


def test_generation_is_told_to_copy_placeholders_and_sign_off_with_the_owners_placeholder(monkeypatch):
    prompts = []

    async def capture(system_prompt, user_prompt, **_kwargs):
        prompts.append(system_prompt)
        return "draft"

    monkeypatch.setattr(email_agent, "call_llm", capture)
    asyncio.run(email_agent.generate_reply(context(email_body="Hi [PERSON_1]", sign_off="[PERSON_2]")))
    assert "copy its placeholder exactly" in prompts[0] and "[Your Name]" in prompts[0]
    assert "Sign the reply off with [PERSON_2]" in prompts[0]
