# Integration Status

## Purpose of this document

This records what is wired together end to end across all four components. **The running pipeline
here is a baseline integration, not a final design.** Its job is to demonstrate that Lane A
(listener), Lane B (retrieval/classifier), Lane C (generation), and Lane D (dashboard) all run
together against one shared database and one shared Google account — proof of an integrated system
for Dr Asad.

**Each lane owner is free to redo, replace, or refine their own part** with whatever implementation
they prefer. The seams (`backend/app/contracts.py`, `specs/context/`) are the contract; as long as
a lane keeps to those shapes, it can be rebuilt internally without breaking the others.

## Pipeline

```
Gmail -> listener (mask PII) -> Supabase (messages) -> backend (retrieve + generate) -> dashboard
                                       ^                        |                            |
                                 shared project           approve + edit  <-----------------+
                                       |                        v
                                       +----------------  send reply (Gmail API)
```

A real email flows Gmail -> mask -> shared Supabase -> retrieval -> draft -> dashboard -> approve
-> sent, verified end to end on the shared `aimail.mds25` account.

## Integrated (working)

| Area | Status | Notes |
|------|--------|-------|
| Lane A: Gmail watch + Pub/Sub -> mask -> DB | Working | Idempotent insert (`on_conflict=gmail_message_id`), deduped |
| Shared DB | Working | One Supabase project; migrations 0001–0005 live, 0006–0008 in flight; policy chunks seeded |
| Lane B: retrieval (`/search`, `/ask`) | Working | hit_rate 1.0; MRR 1.0 with query reformulation |
| Lane B: priority classifier | Working | RoBERTa, macro-F1 0.69 on a 120-email human holdout. **Backfill incomplete** — 12 of 27 messages scored, the rest still show the MEDIUM default |
| Lane C: draft generation | Working | Runs on Gemini (~6s); cached per message; only real drafts cached |
| Lane C: pre-generation | Working | Background poller + `make generate` so opens are instant |
| Lane C: regenerate / refine / tone | Working | `POST /emails/{id}/regenerate` (tone), `/refine`; agent `/refine` |
| Send: Approve & Send | Working | `POST /emails/{id}/send` replies via Gmail API; idempotent; `sent_at` |
| Lane D: dashboard | Working | List, detail, body, priority, draft, regenerate, refine, tone, send |
| Seams | Working | `contracts.py`, `db-schema.md`, `api-contracts.md` kept in sync |
| Auth | Working | Bearer token on every route except `GET /`; dashboard and backend share one `.env` value |
| Tests | 18 backend test files | rag, chunk, eval, temporal, dashboard, config, baseline, auth, personalisation, ... |

## Backend endpoints

- `GET /emails` — inbox list (Lane A fields + Lane B priority)
- `GET /emails/{id}` — detail; generates once and caches
- `POST /emails/{id}/regenerate` — fresh draft in a tone
- `POST /emails/{id}/refine` — revise draft per an instruction
- `POST /emails/{id}/send` — send the approved draft, mark sent
- `POST /search`, `POST /ask` — Lane B retrieval / grounded answer
- `GET/POST /documents`, `POST /documents/upload` — knowledge base
- `GET /system/info` — build and configuration introspection

## Remaining (each is a lane owner's call)

| # | Item | Lane | Why it's open |
|---|------|------|---------------|
| 1 | Prompt-injection fencing | C | The last critical security gap. Untrusted email text is interpolated straight into every prompt, including the critic's. |
| 2 | Chrome extension wiring | D | The panel renders live data on the `/extension` route; the MV3 shell and Gmail content script are not built. |
| 3 | Attachment OCR | A | No code yet. Image parts are never fetched, so a screenshot's contents never reach retrieval. |
| 4 | Importance backfill | B | Classifier is trained; 15 of 27 messages are still unscored, so most badges show the MEDIUM default. |
| 5 | Reply threading | A + B | Approved replies send as standalone mail. Migration 0009 specced; needs Lane A to capture Gmail's thread ID and the RFC message ID. |
| 6 | Critic gate redesign | C | The review gate has never fired — see below. Four purpose-built gates proposed to replace one self-graded score. |
| 7 | Send hardening | A / infra | Reuses the listener's OAuth token; best practice is a Workspace service account with domain-wide delegation. |
| 8 | Gmail watch renewal | A | The watch expires ~7 days and nothing renews it; restarting the listener re-arms it. |
| 9 | PII masking refinement | A | **JiaJun is actively refining this — do not touch.** Regex tuning against Presidio, targeting the 80% floor. |
| 10 | Drafts page | D | **Han is actively working on this — do not touch.** |
| 11 | n8n | — | Not used — the backend sends via the Gmail API directly. The `n8n/` folder is scaffolding kept as evidence of the pivot. |

## What has been measured

| Component | Method | Result |
|-----------|--------|--------|
| PII masking | labelled fixture, 38 spans + 10 negative controls | 38/38 spans caught |
| Retrieval | 8-query eval set over real codes of conduct | hit rate 1.00, MRR 0.82 |
| Priority classifier | 120-email human-labelled holdout, macro-F1 | 0.69 (roughly +/-9% at this sample size) |
| Critic gate | 55 runs through `make eval-critic` | **0 of 43 drafts ever scored below the 0.8 review threshold** |

The critic result is a finding, not a pass: the gate has never fired. The refine loop repairs any
low score before the flag is evaluated, the four underlying checks (grounding, PII, tone,
completeness) are computed and then discarded, and the gate reads only a self-reported scalar.
This reproduces documented failure modes — verbalized-confidence miscalibration and self-preference
bias in LLM-as-a-judge — so it is written up as a replication rather than a defect.

## How to run the whole thing

```bash
make dev        # everything: Presidio, backend :8000, agent :8001, dashboard :8090, listener
```

Open <http://localhost:8090>. Stop with Ctrl+C, never Ctrl+Z — a suspended stack keeps holding the
ports and every request then times out in a way that looks like an application bug.

Individually, if you want one service at a time:

```bash
make backend    # :8000  API + background pre-generation
make agent      # :8001  Lane C generation (127.0.0.1 only)
make web        # :8090  dashboard
cd listener && go run .   # Lane A (needs credentials.json + token.json + shared .env)
```

First-time DB setup: `make migrate` then `make seed`. See the root `README.md` for details.
