# CLAUDE.md — AImail

Instructions for Claude Code agents working in this repository.

## Project overview

AImail is an AI-powered corporate email assistant. It reads full email threads, learns the user's writing style, generates context-aware reply drafts, and routes everything through PII masking before reaching the Claude API. Drafts surface in a dashboard for human approval before being sent.

## Architecture summary

Four components, one per top-level folder:

1. **`n8n/`** — n8n workflows (exported JSON). Watches Gmail; fires a webhook on new mail; sends approved replies.
2. **`listener/`** — small HTTP service that receives the n8n webhook and forwards to the backend. Python first, Go later.
3. **`backend/`** — Python FastAPI. PII masking, Claude API calls, multi-agent pipeline, Postgres + pgvector reads/writes, REST endpoints.
4. **`frontend/`** — Next.js + TypeScript + Tailwind dashboard. Talks to backend via REST only.

Flow: `Gmail → n8n → listener → backend → frontend → user approves → backend → n8n → Gmail`.

## Folder ownership

| Folder       | Service   |
|--------------|-----------|
| `n8n/`       | n8n       |
| `listener/`  | listener  |
| `backend/`   | backend   |
| `frontend/`  | frontend  |
| `infra/`     | infra/devops |
| `specs/`     | shared — specs are the contract |
| `docs/adr/`  | architecture decision records |

Do not modify another service's folder without flagging it in your response. Cross-service changes (e.g. an API contract change) must be reflected in `specs/context/api-contracts.md` first.

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

When you finish exploring a service or subsystem for the first time, **offer** to add a short summary to `AI_DOCS/<name>.md` — architecture overview, key files, gotchas, common operations. Never write `AI_DOCS/` entries without explicit human approval; this keeps the repo clean while giving future sessions a warm start.
