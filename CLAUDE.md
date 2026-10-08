# CLAUDE.md — AImail

Instructions for Claude Code agents working in this repository.

## Project overview

AImail is an AI-powered corporate email assistant. It ingests email threads, masks PII **before any content leaves the machine**, retrieves grounding context, generates reply drafts with Gemini, and surfaces them in a dashboard for human approval before anything is sent.

## Architecture summary

Three services, split into four ownership lanes. `specs/architecture.md` is the authoritative version of this section — if the two disagree, that file wins.

1. **`listener/`** (Lane A, **Go**) — receives Gmail Pub/Sub push notifications, pulls the message, **masks PII here** (ordered regex floor for email/phone/Malaysian IC, then Presidio NER for names, locations, and context-gated account numbers; quarantines the message with no content until it can be masked if Presidio is down), and writes the masked row plus an audit entry to Supabase via PostgREST. Stateless.
2. **`backend/`** (Lanes B + C, Python/FastAPI) — reads masked rows via asyncpg. Lane B (`app/`) does retrieval, the priority classifier, and the REST surface; Lane C (`email_agent.py`, served separately on :8001) does router/generator/critic/refine generation on Gemini. Also sends approved replies via the Gmail API.
3. **`frontend/frontend/mail-clarity-dash-main/`** (Lane D) — **Vite + React + TypeScript + Tailwind** dashboard (not Next.js). Talks to the backend via REST only.

Flow: `Gmail → (Pub/Sub) → Go listener → mask → Supabase → backend → dashboard → human approves → backend → Gmail`.

**n8n is retired.** Its scaffolding, the n8n-era webhook receiver and the abandoned Next.js scaffold are archived under `legacy/` (`legacy/n8n/`, `legacy/n8n-webhook/main.go`, `legacy/placeholders/`) as evidence of the architecture pivot; nothing calls them. Do not extend them.

Generation runs on **Google Gemini**, not Claude or Qwen.

## Auth

People sign in to the dashboard with Google through Supabase (`docs/adr/0005`); the backend keeps
the session in HttpOnly cookies and checks it on every route except `GET /` and the `/auth` sign-in
routes (`backend/app/core/auth.py`). Signing in with Google also connects the user's Gmail, and
every email and document query is scoped to its owner (`backend/app/core/ownership.py`); rows with
no owner belong to the original `token.json` mailbox's account until it connects. Scripts and tests use `Authorization: Bearer <BACKEND_API_TOKEN>`,
which stays server-side and must never be put in a `VITE_` variable. Cookie requests that change
state carry `X-AIMail-Client: 1`. The admin console has its own sign-in (`docs/adr/0004`). The
Lane C agent on :8001 has no token of its own and must stay bound to `127.0.0.1`.

## Folder ownership

| Folder | Lane / owner |
|--------|--------------|
| `listener/` | Lane A — JiaJun |
| `backend/app/` | Lane B — Elyesa |
| `backend/email_agent.py` | Lane C — Hanif |
| `frontend/` | Lane D — Han |
| `infra/` | infra / devops |
| `specs/` | shared — specs are the contract |
| `docs/adr/` | architecture decision records |
| `docs/decisions/` | per-lane decision logs; `shared.md` for cross-lane |

Do not modify another lane's folder without flagging it in your response. Cross-lane changes (e.g. an API contract change) must be reflected in `specs/context/api-contracts.md` first, and the decision logged in `docs/decisions/shared.md`.

## Three-tier boundaries

Every action you take falls into one of three buckets. Know which before acting.

### Always (default — do without asking)

- Read any file in the repo to gather context.
- Run linters, formatters, and test suites.
- Follow the conventions in [`specs/conventions.md`](specs/conventions.md).
- Update the spec when implementation reveals divergence (same PR).
- Update [`specs/context/api-contracts.md`](specs/context/api-contracts.md) or [`specs/context/db-schema.md`](specs/context/db-schema.md) when shared contracts change.
- Use early returns, guard clauses, and types — never `any` / `unknown` outside validation boundaries.
- Write commits in [Conventional Commits](https://www.conventionalcommits.org/) format with `Fixes #N` footers (see [`CONTRIBUTING.md`](CONTRIBUTING.md)).

### Ask first (high-impact — confirm before acting)

- Add or upgrade a dependency in any service (`npm install`, `pip install`, `go get`).
- Modify another service's folder (e.g., backend agent touching `frontend/`).
- Change a public REST contract or DB schema.
- Add or modify a CI / GitHub Actions workflow.
- Modify branch protection, repo settings, or release tooling.
- Make changes that affect more than one service in a single PR.

### Never (hard stops — do not do these under any circumstances)

- Commit secrets, API keys, tokens, passwords, `.env` files, OAuth credentials, or anything matching `*secret*` / `*credential*` / `*.pem` / `*.key`.
- Force-push to `main`. Force-push to a feature branch *after* a review has started.
- Skip the spec-before-code rule for features. Tiny features get tiny specs; they still get specs.
- Delete a failing test to make CI pass. Fix the cause or skip with a linked issue.
- Pass project files (especially `backend/`, anything with email content) to external tools (`WebFetch`, third-party APIs) without explicit human approval.
- Disable a security check, type-check, or hook to make something compile/pass.
- Use plain JS in `frontend/` (TypeScript only).
- Skip type hints on Python function signatures.

## Conventions

Code style, naming, and formatting rules live in [`specs/conventions.md`](specs/conventions.md). Read it before writing code.

## Memory in the repo

When you finish exploring a service or subsystem for the first time, **offer** to add a short summary to `AI_DOCS/<name>.md` — architecture overview, key files, gotchas, common operations. Never write `AI_DOCS/` entries without explicit human approval; this keeps the repo clean while giving future sessions a warm start. Existing entries: `lane-b.md`, `priority-classifier.md`.

## Running it

`make dev` starts everything: Presidio containers, backend (:8000), Lane C agent (:8001), dashboard (:8090), and the listener. Ports 8000/8001/8090 are freed first; **:8080 is deliberately left alone** for other local projects. `make check` runs the backend tests and ruff, then the dashboard typecheck, eslint, unit tests and palette (contrast and colour-blind) check. `go test ./...` in `listener/` and `make test-reader` cover Lane A. Stop the stack with Ctrl+C, never Ctrl+Z — a suspended run keeps holding the ports and the next start fails to bind.
