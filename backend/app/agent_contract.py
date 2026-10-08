"""The contract between the backend and the agent (:8001): one set of models both sides import.

Each used to keep its own copy (the agent's Pydantic models, the backend's hand-built dicts), and they
drifted: refine lost the tone and some review reasons. The backend builds these models to call the agent
and validates every answer against them, so a field changed on one side breaks a test, not production.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.providers import Provider

# The agent refuses longer translations; the backend checks first so the user gets a clear answer.
MAX_TRANSLATE_CHARS = 12_000


class Tone(StrEnum):
    PROFESSIONAL = "professional"
    CASUAL = "casual"


TONE_PROMPTS: dict[Tone, str] = {
    Tone.PROFESSIONAL: "professional, concise, and collaborative",
    Tone.CASUAL: "casual, warm, and friendly",
}
DEFAULT_TONE_PROMPT = TONE_PROMPTS[Tone.PROFESSIONAL]


class ProcessEmailRequest(BaseModel):
    thread_context: str
    email_body: str
    rag_context: str          # stub input standing in for Lane B's retrieval, for now
    tone: str = DEFAULT_TONE_PROMPT
    # The owner's name as a placeholder ([PERSON_n]), never the name itself; "" for no sign-off.
    sign_off: str = ""
    # The user's writing style (specs/features/writing-profile.md), masked before it was stored.
    style_hint: str = ""
    style_examples: list[str] = Field(default_factory=list)
    # Required: a caller that forgets it must fail, not silently send the email to the cloud.
    provider: Provider


class ProcessEmailResponse(BaseModel):
    category: str
    draft: str | None = None
    confidence: float | None = None
    issues: list[str] = Field(default_factory=list)
    summary: str
    action_items: list[str] = Field(default_factory=list)
    attempts: int = 0
    needs_human_review: bool = False
    # The critic already computes these; returning them is what lets the gate read something
    # concrete instead of a self-reported scalar with no definition.
    grounding_ok: bool | None = None
    pii_clean: bool | None = None
    tone_match: bool | None = None
    completeness: bool | None = None
    pii_findings: list[str] = Field(default_factory=list)
    unsupported_specifics: list[str] = Field(default_factory=list)
    unaddressed_requests: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    # Every model attempt this draft made: model, outcome, milliseconds, provider.
    model_calls: list[dict] = Field(default_factory=list)
    # Every prompt that left for a model (model_gateway.Egress): no text, only what and how much.
    egress: list[dict] = Field(default_factory=list)
    # Which wording of the prompts wrote this draft (email_agent.PROMPT_VERSION).
    prompt_version: str = ""


class TranslationLanguage(StrEnum):
    ENGLISH = "en"
    MALAY = "ms"
    CHINESE = "zh"



class TranslateRequest(BaseModel):
    text: str = Field(max_length=MAX_TRANSLATE_CHARS)
    language: TranslationLanguage
    # Required: a caller that forgets it must fail, not silently send the email to the cloud.
    provider: Provider


class RefineRequest(BaseModel):
    email_body: str
    draft: str
    instruction: str
    tone: str = DEFAULT_TONE_PROMPT
    # What the critic needs to judge the revision the way it judged the original draft.
    thread_context: str = ""
    rag_context: str = ""
    action_items: list[str] = Field(default_factory=list)
    sign_off: str = ""
    style_hint: str = ""
    style_examples: list[str] = Field(default_factory=list)
    # Required: a caller that forgets it must fail, not silently send the email to the cloud.
    provider: Provider


class RefineResponse(BaseModel):
    draft: str
    confidence: float | None = None
    issues: list[str] = Field(default_factory=list)
    needs_human_review: bool = False
    grounding_ok: bool | None = None
    pii_clean: bool | None = None
    tone_match: bool | None = None
    completeness: bool | None = None
    pii_findings: list[str] = Field(default_factory=list)
    unsupported_specifics: list[str] = Field(default_factory=list)
    unaddressed_requests: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    model_calls: list[dict] = Field(default_factory=list)
    egress: list[dict] = Field(default_factory=list)
    prompt_version: str = ""


class TranslateResponse(BaseModel):
    language: TranslationLanguage
    text: str
    egress: list[dict] = Field(default_factory=list)
