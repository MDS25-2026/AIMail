# Pitch demo run sheet (2-3 min)

Six beats, ~25 seconds each. Send the test email 30-60 s before starting so Pub/Sub has
already fired. Two tabs pre-loaded: Supabase row, dashboard (localhost:8090).

| Beat | On screen | Say |
|------|-----------|-----|
| Ingest | Listener log line | "R01, captured via Pub/Sub push, no polling." |
| Mask | Raw body beside stored `body_masked` | "R02. This is the privacy boundary. It runs before anything leaves our server." |
| Triage | Priority, summary, action items | "R05.1, trained classifier scored against human labels, not a prompt." |
| Ground | Draft with retrieved policy chunk visible | "R03.2, the draft is traceable to that retrieved chunk." |
| Gate | Critic confidence score | "R03.7, below threshold it never reaches the user." |
| Send | Click Approve & Send, mail lands | "R04.4. There is no code path that sends without this click." |

The mask beat is the money shot; give it an extra beat of silence. Skip conversational
refine (R04.2) - most likely beat to hang on a live API call, proves nothing the others don't.

## Prep checklist (before rehearsal)

0. **Set `BACKEND_API_TOKEN` and `VITE_BACKEND_API_TOKEN` to the same value in `.env`** or the
   backend fails closed and every request returns 503. Generate:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Restart the dashboard after
   changing it - Vite bakes env vars in at build time.
1. `make dev` (starts Presidio containers, backend :8000, agent :8001, dashboard :8090,
   listener). Wait for "Gmail Watch established!".
2. **Backfill priorities or the Triage beat lies.** `priority_label(None)` renders MEDIUM for
   every row until the classifier has scored it. From `backend/`:
   `python scripts/backfill_importance.py` (PRIORITY_MODEL=distilbert is set in .env).
3. Mask-beat SQL for the Supabase tab:
   `select from_addr, subject, body_masked, emails_masked, phones_masked from messages order by received_at desc limit 1;`
4. Pre-generate drafts for the showcase emails (Gemini free tier 429s mid-refine).
5. Demo mailbox only as sender and recipient - Approve & Send dispatches real Gmail.
6. Record the fallback video. If used, one line: "live run flaked, here is the recording."
7. Full round-trip rehearsal at least once, same machine, same network.

## Corrections to the original sheet

- "body_masked vs masked_body still open" is stale: code was already unified and the docs
  were closed 2026-08-31 (`docs/decisions/shared.md`). The pre-rehearsal round-trip still
  stands as the verification.
- The Triage beat's claim depends on prep step 2 having run - it is not true by default.

## What not to claim

- No Chrome extension, no OCR demo or implication. Both live on the Next Steps slide, where
  being upfront counts in your favour.
- No "80% masking accuracy" - that is an acceptance criterion, not a result. Safe line:
  "target is 80%, measurement harness lands this sprint." The follow-up to any stated metric
  is "measured how, on what set."

## Q&A crib (verified against the repo, 2026-08-31)

- **"Can anyone hit your send endpoint right now?"** No - as of 2026-09-01 every route except
  `GET /` requires `Authorization: Bearer <BACKEND_API_TOKEN>`; an unauthenticated POST to
  `/emails/{id}/send` returns 401, and 6 tests in `backend/tests/test_auth.py` pin it. Read
  routes are gated too, since they return masked email content. Volunteer the limitation before
  it is asked: it is one shared token, and the frontend copy ships in the Vite bundle, so it
  authenticates the client, not a user. Per-user Supabase JWTs replace one file
  (`app/core/auth.py`) and are deferred because AImail serves a single shared mailbox.
  Live proof, if asked to show it:
  `curl -si -X POST localhost:8000/emails/x/send -H 'Content-Type: application/json' -d '{"draft":"hi"}' | head -1`
- **"How do you know the masking works?"** 13 tests in `listener/`, plus a recall harness
  (`recall_test.go`) scoring a labeled corpus of 31 cases / 37 PII spans: currently **37/37
  against the 80% R02 target**, and it scores the regex layer alone when Presidio is down so an
  offline run never reports the full number. Covered: email, MY and US phone formats, IC
  (dashed, space-separated, and bare date-gated), PERSON, LOCATION, context-gated
  ACCOUNT_NUMBER (live-verified 0.75 vs the 0.6 threshold).
- **"Measured how, on what set?"** - the honest follow-up, and the answer must include this:
  the corpus is team-authored, so 100% means "no known failure mode is unhandled", not "no PII
  escapes". It was hardened by adversarial probing (the space-separated IC and `+60 (12)`
  phone forms were found that way and fixed), and the remaining known leaks are stated below.
  Independent test data is the next step.
- **Known leaks, stated before being asked.** By design: an account number with no nearby
  context word ("send it to 512837465920") stays visible - the context gate is what stops every
  invoice number being masked; ORGANIZATION names are off deliberately, since masking company
  names degrades draft quality. Genuine limitations: person names that are also common words
  ("April will handle it"), and Malaysian street types the English NER model does not know
  ("Persiaran Gurney" masks, "Jalan" forms mask, but coverage is uneven).
- **"How would you prove no unauthorized send happened?"** The `audit_log` table now carries the
  whole pipeline, not just ingestion: Lane A writes `setup_watch` / `fetch_message` /
  `store_message`, and Lane B writes `generate_draft`, `refine_draft`, and `approve_and_send`
  (including a `success=false` row when Gmail rejects the send). Rows hold message IDs only,
  never email content. Query for the tab if asked:
  `select created_at, action, success, detail from audit_log order by created_at desc limit 20;`
  Honest limitation: rows record the action, not *which human* did it - one shared token means
  there is no per-user actor yet. That arrives with per-user auth.
- **"What if Presidio dies?"** Degrades to the regex floor, never stores raw text. Proven by
  test with the analyzer unreachable, and the audit row records "presidio degraded".
- **"Why a trained classifier instead of asking the LLM?"** Cost, latency, reproducibility,
  and it is measurable - F1 against a human-labeled holdout (0.69, up from 0.57 after
  rubric-consistent relabeling). A prompt is none of those.
