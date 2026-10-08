"""Shared builders for the agent's drafting tests: a context, a critic verdict, a judged draft."""

from email_agent import Candidate, CriticVerdict, DraftContext

GOOD_VERDICT = {"confidence": 0.92, "grounding_ok": True, "pii_clean": True, "tone_match": True,
                "completeness": True, "issues": [], "unaddressed_items": []}


def context(**overrides: object) -> DraftContext:
    fields = {"thread_context": "", "rag_context": "", "email_body": "Hi", "tone": "professional",
              "action_items": []} | overrides
    return DraftContext(**fields)


def verdict(**overrides: object) -> CriticVerdict:
    return CriticVerdict.model_validate(GOOD_VERDICT | overrides)


def candidate(draft: str = "Draft", *, pii: list[str] | None = None, specifics: list[str] | None = None,
              unaddressed: list[str] | None = None, judged: bool = True, **verdict_fields: object) -> Candidate:
    return Candidate(draft=draft, verdict=verdict(**verdict_fields) if judged else None,
                     pii_findings=pii or [], specifics=specifics or [], unaddressed=unaddressed or [])
