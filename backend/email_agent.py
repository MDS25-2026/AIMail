import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field
from huggingface_hub import InferenceClient

load_dotenv()

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")

hf_client = InferenceClient(provider="auto", api_key=HF_TOKEN)

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


# ---------- Gemini helper (async, reusable) ----------

async def call_gemini(prompt: str, response_schema: dict | None = None) -> dict | str:
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if response_schema:
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json", "X-goog-api-key": GOOGLE_API_KEY},
            json=payload,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    return json.loads(text) if response_schema else text.strip()


# ---------- Qwen helper (sync client, bridged to async) ----------

async def call_qwen(system_prompt: str, user_prompt: str, max_tokens: int = 1020) -> str:
    def _sync_call():
        response = hf_client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    return await asyncio.to_thread(_sync_call)


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
        return await call_qwen(system_prompt, user_prompt)

    if category == "COMPLEX":
        # NOTE: using Qwen for now to demonstrate multi-provider flexibility.
        # Swap to Claude Sonnet here later — same function signature, just a different call.
        return await call_qwen(system_prompt, user_prompt, max_tokens=2000)

    raise ValueError(f"generate_reply() called with unsupported category: {category}")


# ---------- Stage 3: Critic ----------

async def evaluate_reply(thread_context: str, rag_context: str, email_body: str,
                          generated_reply: str, tone: str) -> dict:
    prompt = f"""You are a Critic Agent for an email assistant. Your job is to review a generated email reply BEFORE it is shown to the human user for approval.

Evaluate the reply against these checks:

1. grounding_ok: Does the reply ONLY use information present in the retrieved sources / thread context? Flag as false if it introduces facts, names, dates, or commitments not found in the context (hallucination).
2. pii_clean: Does the reply avoid leaking any personally identifiable information (emails, phone numbers, addresses, full names of third parties) that should have been masked?
3. tone_match: Does the reply match the requested tone ({tone})?
4. completeness: Does the reply address all questions/action items raised in the latest email and thread?

Then provide an overall confidence score between 0.0 and 1.0 representing how safe this reply is to auto-suggest for sending.

List any specific issues found, in plain language. If there are no issues, return an empty list.

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
            "grounding_ok": {"type": "boolean"},
            "pii_clean": {"type": "boolean"},
            "tone_match": {"type": "boolean"},
            "completeness": {"type": "boolean"},
            "issues": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["confidence", "grounding_ok", "pii_clean", "tone_match", "completeness", "issues"],
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

    return await call_qwen(system_prompt, user_prompt, max_tokens=2000)


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
    return await call_qwen("You summarize emails concisely.", user_prompt, max_tokens=200)


async def extract_actions(email_body: str) -> list[str]:
    prompt = f"""
Extract action items from this email.

Return ONLY valid JSON in this format:
{{"action_items": ["...", "..."]}}

EMAIL:
{email_body}
"""
    raw = await call_qwen("You extract structured JSON only.", prompt, max_tokens=300)
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw).get("action_items", [])
    except json.JSONDecodeError:
        return []


# ---------- Orchestrator endpoint ----------

MAX_REFINE_ATTEMPTS = 3
CONFIDENCE_THRESHOLD = 0.8


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
        )

    draft = await generate_reply(category, req.thread_context, req.rag_context, req.email_body, req.tone)
    evaluation = await evaluate_reply(req.thread_context, req.rag_context, req.email_body, draft, req.tone)

    attempts = 0
    while evaluation.get("confidence", 0.0) < CONFIDENCE_THRESHOLD and attempts < MAX_REFINE_ATTEMPTS:
        draft = await refine_reply(req.thread_context, req.rag_context, req.email_body, draft, evaluation)
        evaluation = await evaluate_reply(req.thread_context, req.rag_context, req.email_body, draft, req.tone)
        attempts += 1

    return ProcessEmailResponse(
        category=category,
        draft=draft,
        confidence=evaluation.get("confidence"),
        issues=evaluation.get("issues", []),
        summary=summary,
        action_items=action_items,
        attempts=attempts,
        needs_human_review=evaluation.get("confidence", 0.0) < CONFIDENCE_THRESHOLD,
    )