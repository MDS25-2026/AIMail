import asyncio
import json
import os
import re

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

load_dotenv()

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PRESIDIO_ANALYZER_URL = os.getenv("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")

# Greedy decoding for reproducibility. Note this reduces sampling randomness but does not
# guarantee determinism — batch-dependent reduction kernels vary run to run regardless.
GENERATION_TEMPERATURE = 0.0

app = FastAPI()


# ---------- Pydantic schemas: request/response contract ----------

class ProcessEmailRequest(BaseModel):
    thread_context: str
    email_body: str
    rag_context: str          # stub input standing in for Lane B's retrieval, for now
    tone: str = "professional, concise, and collaborative"


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


# ---------- Gemini helper (async, reusable) ----------

async def call_gemini(prompt: str, response_schema: dict | None = None) -> dict | str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": GENERATION_TEMPERATURE},
    }
    if response_schema:
        payload["generationConfig"] |= {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(4):
            resp = await client.post(
                GEMINI_URL,
                headers={"Content-Type": "application/json", "X-goog-api-key": GOOGLE_API_KEY},
                json=payload,
            )
            # Free-tier rate limit (429) is transient — back off and retry before giving up.
            if resp.status_code == 429 and attempt < 3:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            break
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    return json.loads(text) if response_schema else text.strip()


# ---------- LLM helper (Gemini-backed) ----------

async def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1020) -> str:
    # Backed by Gemini. (Formerly call_qwen on HuggingFace, which was rate-limited and flaky.)
    result = await call_gemini(f"{system_prompt}\n\n{user_prompt}")
    return result if isinstance(result, str) else json.dumps(result)


# ---------- Stage 1: Router ----------

async def route_email(thread_context: str, email_body: str) -> str:
    prompt = f"""You are a routing classifier for an email assistant.

Given the email below, classify it into exactly one category.

Categories:
- STANDARD: normal requests, single questions, routine scheduling
- COMPLEX: multi-part questions, sensitive/escalation topics, requires synthesizing multiple sources
- NA: emails that don't fit into any of the above categories

Email thread:
{thread_context}

Latest email:
{email_body}

Respond with only the category name."""

    category = await call_gemini(prompt)
    return category if category in ("STANDARD", "COMPLEX", "NA") else "NA"


# ---------- Stage 2: Reply generation ----------

async def generate_reply(category: str, thread_context: str, rag_context: str,
                          email_body: str, tone: str) -> str:
    user_prompt = f"""
    thread context:
    {thread_context}

    rag context:
    {rag_context}

    latest email:
    {email_body}
    """
    system_prompt = f"you are an email assistant that generates {tone} email replies."

    if category == "STANDARD":
        return await call_llm(system_prompt, user_prompt)

    if category == "COMPLEX":
        # NOTE: using Qwen for now to demonstrate multi-provider flexibility.
        # Swap to Claude Sonnet here later — same function signature, just a different call.
        return await call_llm(system_prompt, user_prompt, max_tokens=2000)

    raise ValueError(f"generate_reply() called with unsupported category: {category}")


# ---------- Stage 3: Critic ----------

async def evaluate_reply(thread_context: str, rag_context: str, email_body: str,
                          generated_reply: str, tone: str,
                          action_items: list[str] | None = None) -> dict:
    items = action_items or []
    numbered_items = "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1)) or "(none extracted)"
    prompt = f"""You are a Critic Agent for an email assistant. Your job is to review a generated email reply BEFORE it is shown to the human user for approval.

Evaluate the reply against these checks:

1. grounding_ok: Does the reply ONLY use information present in the retrieved sources / thread context? Flag as false if it introduces facts, names, dates, or commitments not found in the context (hallucination).
2. pii_clean: Does the reply avoid leaking any personally identifiable information (emails, phone numbers, addresses, full names of third parties) that should have been masked?
3. tone_match: Does the reply match the requested tone ({tone})?
4. completeness: Does the reply address all questions/action items raised in the latest email and thread?
   The requests already extracted from this email are numbered below. For each one, decide whether
   the reply addresses it, and return the numbers of any it does NOT address in unaddressed_items.
   If the list is empty, judge completeness from the email text alone and return an empty list.

Then provide an overall confidence score between 0.0 and 1.0 representing how safe this reply is to auto-suggest for sending.

List any specific issues found, in plain language. If there are no issues, return an empty list.

Extracted requests:
{numbered_items}

Thread context:
{thread_context}

RAG context:
{rag_context}

Latest email:
{email_body}

Generated reply to review:
{generated_reply}

Respond only with the evaluation."""

    schema = {
        "type": "object",
        "properties": {
            "confidence": {"type": "number"},
            "unaddressed_items": {"type": "array", "items": {"type": "integer"}},
            "grounding_ok": {"type": "boolean"},
            "pii_clean": {"type": "boolean"},
            "tone_match": {"type": "boolean"},
            "completeness": {"type": "boolean"},
            "issues": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["confidence", "grounding_ok", "pii_clean", "tone_match", "completeness",
                     "issues", "unaddressed_items"],
    }

    return await call_gemini(prompt, response_schema=schema)


# ---------- Stage 4: Refine ----------

async def refine_reply(thread_context: str, rag_context: str, email_body: str,
                        generated_reply: str, evaluation_feedback: dict) -> str:
    user_prompt = f"""
    evaluation feedback:
    {evaluation_feedback}

    thread context:
    {thread_context}

    rag context:
    {rag_context}

    latest email:
    {email_body}

    draft reply:
    {generated_reply}
    """
    system_prompt = "you are an email assistant that improves the draft email reply in accordance with the evaluation feedback, ensuring it is professional, concise, and collaborative."

    return await call_llm(system_prompt, user_prompt, max_tokens=2000)


# ---------- Stage 5: Summary + action items ----------

async def extract_summary(email_body: str, thread_context: str, rag_context: str) -> str:
    user_prompt = f"""
    Summarize the following email thread in 2-3 sentences for a busy professional.

    thread context:
    {thread_context}

    rag context:
    {rag_context}

    latest email:
    {email_body}
    """
    return await call_llm("You summarize emails concisely.", user_prompt, max_tokens=200)


async def extract_actions(email_body: str) -> list[str]:
    email_body = strip_quoted(email_body)
    prompt = f"""
Extract action items from this email.

Return ONLY valid JSON in this format:
{{"action_items": ["...", "..."]}}

EMAIL:
{email_body}
"""
    raw = await call_llm("You extract structured JSON only.", prompt, max_tokens=300)
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw).get("action_items", [])
    except json.JSONDecodeError:
        return []



# ---------- Gate 1: deterministic PII scan over the generated draft ----------

# Malaysia has no predefined Presidio recognizer, so these are supplied ad-hoc per request
# rather than baked into the container image. Scores are deliberately low and lifted by the
# context words, the same approach Presidio documents for weak patterns.
_AD_HOC_RECOGNIZERS = [
    {"name": "MY_NRIC", "supported_language": "en", "supported_entity": "MY_NRIC",
     "patterns": [{"name": "nric", "regex": r"\b\d{6}[- ]?\d{2}[- ]?\d{4}\b", "score": 0.4}],
     "context": ["ic", "nric", "mykad", "identity card"]},
    {"name": "MY_PHONE", "supported_language": "en", "supported_entity": "MY_PHONE",
     "patterns": [{"name": "my_mobile", "regex": r"\b(?:\+?60|0)1\d[- ]?\d{3,4}[- ]?\d{4}\b", "score": 0.6}],
     "context": ["call", "phone", "mobile", "tel", "hp"]},
]

# Format-clear types only. PERSON and LOCATION are excluded deliberately: a draft legitimately
# contains salutations and place names, so gating on them would block good replies.
_PII_ENTITIES = ["EMAIL_ADDRESS", "CREDIT_CARD", "IBAN_CODE", "MY_NRIC", "MY_PHONE"]
_PII_SCORE_THRESHOLD = 0.5

# A redaction token reaching a sent reply is its own failure, and regex catches it for free.
_PLACEHOLDER = re.compile(r"\[[A-Z_]+_REDACTED\]")


async def scan_draft_pii(draft: str) -> list[str]:
    """Entity types found in the draft. Empty means clean.

    The model only ever sees masked text, so any format-clear PII here was invented or leaked.
    Scanning the draft rather than the input is also what catches memorised PII the masking
    layer never had the chance to remove.

    Degrades like the listener does: if Presidio is unreachable the placeholder check still
    runs, and the caller is told the scan was partial rather than being handed a false clean.
    """
    findings = ["REDACTION_PLACEHOLDER"] if _PLACEHOLDER.search(draft) else []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(PRESIDIO_ANALYZER_URL, json={
                "text": draft, "language": "en",
                "score_threshold": _PII_SCORE_THRESHOLD,
                "entities": _PII_ENTITIES,
                "ad_hoc_recognizers": _AD_HOC_RECOGNIZERS,
            })
            resp.raise_for_status()
            findings += sorted({hit["entity_type"] for hit in resp.json()})
    except (httpx.HTTPError, KeyError, ValueError):
        findings.append("PRESIDIO_UNAVAILABLE")
    return findings


# ---------- Quoted-history stripping, for action extraction only ----------

# Zoning lifted request detection from 72.28% to 83.76% accuracy in Lampert, Dale and Paris
# (NAACL-HLT 2010). Quoted history carries requests made to someone else, or already answered.
_QUOTE_MARKER = re.compile(
    r"^[ \t]*(?:-{2,}[ \t]*(?:Original Message|Forwarded by|Forwarded Message)\b.*"
    r"|From:[ \t]\S.*"
    r"|On\b.{0,80}\bwrote:[ \t]*"
    r"|>.*)$",
    re.IGNORECASE | re.MULTILINE,
)
# Low on purpose: "Please review the deck." is a real message body. This only catches the
# forward-with-no-comment case, where stripping leaves nothing to extract from.
_MIN_KEPT_CHARS = 15


def strip_quoted(text: str) -> str:
    """Keep only the new message body.

    Falls back to the full text when stripping would leave almost nothing — a forward-only
    email is all quoted history, and an empty body extracts nothing at all rather than
    extracting the wrong thing.
    """
    match = _QUOTE_MARKER.search(text)
    if not match:
        return text.strip()
    kept = text[:match.start()].strip()
    return kept if len(kept) >= _MIN_KEPT_CHARS else text.strip()



# ---------- Gate 2 (partial): deterministic specifics check ----------

# Value substitution is the hallucination class that matters in business email: RM500 becoming
# RM5,000, "30 days" becoming "60 days", an invoice number off by a digit. Embeddings are
# documented to miss it entirely because the wrong number is topically identical to the right
# one, so this is string comparison rather than a model. It is an engineering augmentation,
# not a published metric — do not cite it as one.
# Thousands separators are removed before matching, so 18,400.00 and 18400 compare equal and
# the pattern never has to allow digits and commas in one repetition. That ambiguity is what
# made the previous version a polynomial-backtracking risk (CodeQL, high) on text an outside
# party controls. Both parts below are fixed-width or unambiguous.
_THOUSANDS_SEPARATOR = re.compile(r"(?<=\d),(?=\d)")
_NUMERIC = re.compile(r"\d+(?:\.\d+)?")


def _trim_zeros(token: str) -> str:
    return token.rstrip("0").rstrip(".") if "." in token else token


def _numbers_in(text: str) -> set[str]:
    """Comparable numeric values, separators removed and trailing decimal zeros trimmed."""
    return {_trim_zeros(t) for t in _NUMERIC.findall(_THOUSANDS_SEPARATOR.sub("", text))}


def unsupported_specifics(draft: str, *sources: str) -> list[str]:
    """Numbers asserted in the draft that appear nowhere in the source material.

    Single digits are skipped: they are almost always prose counts ("your 2 questions")
    rather than facts carried over, and flagging them buries the real findings.
    """
    known = set().union(*(_numbers_in(source) for source in sources))
    return sorted(v for v in _numbers_in(draft) if len(v.lstrip("0")) >= 2 and v not in known)


# ---------- Orchestrator endpoint ----------

MAX_REFINE_ATTEMPTS = 3

# Split deliberately. One constant previously drove both the repair loop and the review flag, so
# the loop resolved anything that would have tripped the flag and the gate never fired once in 43
# measured drafts. The review bar sits above the repair bar.
REFINE_THRESHOLD = 0.8
REVIEW_THRESHOLD = 0.9


def clamp_confidence(value: object) -> float | None:
    """Untrusted email text reaches the critic's prompt, so its number is not trusted either."""
    if value is None:
        return None
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return None


def pii_verdict(findings: list[str]) -> bool | None:
    """True clean, False leaking, None unknown — an unreachable scanner is not a clean bill."""
    if [f for f in findings if f != "PRESIDIO_UNAVAILABLE"]:
        return False
    return None if "PRESIDIO_UNAVAILABLE" in findings else True


def unaddressed_requests(evaluation: dict, action_items: list[str]) -> list[str]:
    """The extracted requests the reply did not answer, as text rather than a bare boolean.

    The critic returns 1-based indices and can return ones that do not exist, so anything out
    of range is dropped rather than trusted — a hostile email reaches this prompt too.
    """
    indices = evaluation.get("unaddressed_items") or []
    return [action_items[i - 1] for i in indices
            if isinstance(i, int) and 1 <= i <= len(action_items)]


def build_review_reasons(evaluation: dict, confidence: float | None, attempts: int,
                         pii_findings: list[str], specifics: list[str] | None = None,
                         unaddressed: list[str] | None = None) -> list[str]:
    """Why a human should look. Reads the checks the critic computes, not only its own score.

    tone_match is excluded on purpose: style is advisory, and blocking a correct, PII-clean,
    complete draft because a model dislikes its register is the wrong trade when a human
    approves every send anyway.
    """
    reasons = []
    if pii_findings:
        reasons.append(f"pii: {', '.join(pii_findings)}")
    if specifics:
        reasons.append(f"figures not in source: {', '.join(specifics)}")
    if evaluation.get("grounding_ok") is False:
        reasons.append("grounding check failed")
    if unaddressed:
        reasons.append(f"does not address: {'; '.join(unaddressed)}")
    elif evaluation.get("completeness") is False:
        # Fallback for emails where nothing was extracted to check per-item.
        reasons.append("does not address everything asked")
    if attempts:
        reasons.append(f"needed {attempts} refine round(s)")
    if confidence is None or confidence < REVIEW_THRESHOLD:
        reasons.append(f"confidence {confidence} below {REVIEW_THRESHOLD}")
    return reasons


@app.post("/process-email", response_model=ProcessEmailResponse)
async def process_email(req: ProcessEmailRequest):
    category = await route_email(req.thread_context, req.email_body)

    summary = await extract_summary(req.email_body, req.thread_context, req.rag_context)
    action_items = await extract_actions(req.email_body)

    if category == "NA":
        return ProcessEmailResponse(
            category=category,
            draft=None,
            confidence=None,
            summary=summary,
            action_items=action_items,
            attempts=0,
            needs_human_review=True,
            review_reasons=["no reply drafted"],
        )

    draft = await generate_reply(category, req.thread_context, req.rag_context, req.email_body, req.tone)
    evaluation = await evaluate_reply(req.thread_context, req.rag_context, req.email_body, draft,
                                      req.tone, action_items)

    attempts = 0
    confidence = clamp_confidence(evaluation.get("confidence"))
    while (confidence or 0.0) < REFINE_THRESHOLD and attempts < MAX_REFINE_ATTEMPTS:
        draft = await refine_reply(req.thread_context, req.rag_context, req.email_body, draft, evaluation)
        evaluation = await evaluate_reply(req.thread_context, req.rag_context, req.email_body, draft,
                                          req.tone, action_items)
        confidence = clamp_confidence(evaluation.get("confidence"))
        attempts += 1

    pii_findings = await scan_draft_pii(draft)
    specifics = unsupported_specifics(draft, req.email_body, req.thread_context, req.rag_context)
    unaddressed = unaddressed_requests(evaluation, action_items)
    reasons = build_review_reasons(evaluation, confidence, attempts, pii_findings, specifics, unaddressed)

    return ProcessEmailResponse(
        category=category,
        draft=draft,
        confidence=confidence,
        issues=evaluation.get("issues", []),
        summary=summary,
        action_items=action_items,
        attempts=attempts,
        needs_human_review=bool(reasons),
        grounding_ok=evaluation.get("grounding_ok"),
        pii_clean=pii_verdict(pii_findings),
        tone_match=evaluation.get("tone_match"),
        completeness=evaluation.get("completeness"),
        pii_findings=pii_findings,
        unsupported_specifics=specifics,
        unaddressed_requests=unaddressed,
        review_reasons=reasons,
    )


class RefineRequest(BaseModel):
    email_body: str
    draft: str
    instruction: str
    tone: str = "professional, concise, and collaborative"


@app.post("/refine")
async def refine(req: RefineRequest) -> dict:
    """Revise an existing draft per a free-text user instruction (dashboard's Refine box)."""
    system_prompt = (
        "You revise an email reply following the user's instruction. "
        "Return only the revised reply, with no preamble."
    )
    user_prompt = (
        f"Original email:\n{req.email_body}\n\n"
        f"Current draft:\n{req.draft}\n\n"
        f"Instruction: {req.instruction}\n\n"
        f"Keep the tone {req.tone}."
    )
    revised = await call_llm(system_prompt, user_prompt, max_tokens=1020)
    return {"draft": revised}