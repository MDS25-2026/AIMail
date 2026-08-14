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
| Shared DB | Working | One Supabase project; migrations 0001–0005; policy chunks seeded |
| Lane B: retrieval (`/search`, `/ask`) | Working | hit_rate 1.0; MRR 1.0 with query reformulation |
| Lane B: priority badge | Placeholder | `importance` NULL -> MEDIUM default; needs a trained model (dataset-gated) |
| Lane C: draft generation | Working | Runs on Gemini (~6s); cached per message; only real drafts cached |
| Lane C: pre-generation | Working | Background poller + `make generate` so opens are instant |
| Lane C: regenerate / refine / tone | Working | `POST /emails/{id}/regenerate` (tone), `/refine`; agent `/refine` |
| Send: Approve & Send | Working | `POST /emails/{id}/send` replies via Gmail API; idempotent; `sent_at` |
| Lane D: dashboard | Working | List, detail, body, priority, draft, regenerate, refine, tone, send |
| Seams | Working | `contracts.py`, `db-schema.md`, `api-contracts.md` kept in sync |
| Tests | 10 backend test files | rag, chunk, eval, temporal, dashboard, config, baseline, ... |

## Backend endpoints

- `GET /emails` — inbox list (Lane A fields + Lane B priority)
- `GET /emails/{id}` — detail; generates once and caches
- `POST /emails/{id}/regenerate` — fresh draft in a tone
- `POST /emails/{id}/refine` — revise draft per an instruction
- `POST /emails/{id}/send` — send the approved draft, mark sent
- `POST /search`, `POST /ask` — Lane B retrieval / grounded answer
- `GET/POST /documents`, `POST /documents/upload` — knowledge base

## Remaining (each is a lane owner's call)

| # | Item | Lane | Why it's open |
|---|------|------|---------------|
| 1 | Priority classifier | B | Needs a labeled dataset; then `make baseline` + `make backfill`. Badge stays MEDIUM until then. |
| 2 | Send hardening | A / infra | Currently reuses the listener's OAuth token; best practice is a Workspace service account with domain-wide delegation. |
| 3 | Gmail watch renewal | A | The watch expires ~7 days; re-running the listener re-arms it. Auto-renew on a timer if long-running. |
| 4 | Thread context | C / A | Generation uses the single email, not the full thread; threads aren't stored/grouped yet. |
| 5 | Extension panel | D | `extension.tsx` handlers are still stubs; it's a secondary preview surface. |
| 6 | n8n | — | Not used — the backend sends via the Gmail API directly. The `n8n/` folder is scaffolding. |
| 7 | Auth | infra | No auth on the API/dashboard; fine for the demo, needed for deployment. |

## How to run the whole thing

```bash
make backend    # :8000  API + background pre-generation
make agent      # :8001  Lane C generation
make web        # :8080  dashboard
cd listener && go run .   # Lane A (needs credentials.json + token.json + shared .env)
```

First-time DB setup: `make migrate` then `make seed`. See the root `README.md` for details.
