# LLM call resilience (Lane C agent + Lane B RAG)

- **Status:** shipped
- **Owner:** veyroxie
- **Related issue:** hackathon-reuse review, items B and C
- **Last updated:** 2026-09-29

## Goal

A draft either finishes within the dashboard's timeout or fails with a named reason. One provider
hiccup (429, 5xx, a stalled socket) no longer costs the draft, and every model reply that feeds
code is structured rather than parsed out of prose.

## Scope

**In scope**
- `backend/gemini_client.py`: one deadline per draft shared by every stage, retries on
  408/429/5xx and transport errors with full-jitter backoff (Retry-After honoured), an optional
  fallback model, a per-model circuit breaker, typed error codes.
- Output caps are actually sent (`maxOutputTokens`); a reply cut off by its cap is an error,
  never a silently truncated draft.
- The router and action extraction use `responseSchema` (enum and array).
- `backend/app/rag/gemini.py`: every SDK client gets a 20 s timeout and two attempts; SDK API
  errors map to the module's own error instead of escaping as a 500.

**Out of scope**
- A non-Gemini fallback provider. Anything outside Google's API is another place masked email
  would travel, and needs its own privacy review.

## Acceptance criteria

- [x] Given a 503 from the primary model, when a fallback is configured, then the fallback answers
      after the primary's retries (`tests/test_gemini_client.py`).
- [x] Given a 400, then no retry is made.
- [x] Given three consecutive failures, then the primary is skipped until the cooldown ends, and
      the last configured model is always tried.
- [x] Given a spent deadline, then no call is made and `/process-email` answers 504 with
      `gemini_deadline_exceeded`; any other Gemini failure answers 503 with its code.
- [x] Given `finishReason: MAX_TOKENS`, then the call raises `gemini_output_truncated`.
- [x] Given a router reply outside the enum, then the category is `NA`.
- [x] Given a 429 from the embeddings API, then `EmbeddingError` is raised
      (`tests/test_gemini_sdk_errors.py`).

## API surface

`/process-email` and `/refine` gain two failure statuses: 503 and 504, body `{"detail": <code>}`.
The dashboard already treats any failure as "leave uncached, retry later", so no caller changes.

## Security & privacy notes

No new destination: the fallback is another Gemini model on the same API and key, so masked text
goes nowhere it did not already go. Log lines carry model names and status codes, never prompts.

## Decisions

- 2026-09-29: deadline defaults to 100 s. Rationale: under the dashboard's 120 s client timeout
  with room for retrieval. Alternatives: per-call timeouts only, which let four slow calls add up
  past the caller's limit.
- 2026-09-29: no lock in the circuit breaker. Rationale: the agent runs on one event loop and
  nothing awaits between a check and its update. Alternatives: a lock, which guards nothing here.
