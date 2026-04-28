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

## Strict rules

- **Never commit secrets.** No API keys, tokens, passwords, or `.env` files. Only `.env.example` is allowed.
- **Python — type hints required** on every function signature and return type. No bare `Any` unless justified at a validation boundary.
- **Frontend — TypeScript only.** No plain `.js`/`.jsx` in `frontend/`.
- **Ask before adding dependencies.** Do not run `npm install`, `pip install`, or `go get` without confirming with the human.
- **Specs before code.** Every feature must have a spec in `specs/features/` (copied from `specs/_template.md`) before implementation begins.
- **Don't cross service boundaries silently.** If a backend change requires a frontend change, say so and stop for confirmation.

## Conventions

Code style, naming, and formatting rules live in [`specs/conventions.md`](specs/conventions.md). Read it before writing code.
