# Tech stack

Pinned versions and authoritative documentation links. Update this file when a version is bumped.

## Backend

| Tech            | Version      | Docs                                                  |
|-----------------|--------------|-------------------------------------------------------|
| Python          | 3.11+        | https://docs.python.org/3/                            |
| FastAPI         | latest 0.x   | https://fastapi.tiangolo.com/                         |
| Pydantic        | 2.x          | https://docs.pydantic.dev/                            |
| SQLAlchemy      | 2.x (async)  | https://docs.sqlalchemy.org/                          |
| asyncpg         | latest       | https://magicstack.github.io/asyncpg/current/         |
| pgvector-python | latest       | https://github.com/pgvector/pgvector-python           |
| Anthropic SDK   | latest       | https://docs.claude.com/en/api/                       |
| ruff            | latest       | https://docs.astral.sh/ruff/                          |
| black           | latest       | https://black.readthedocs.io/                         |

## Listener

| Tech     | Version      | Docs                              |
|----------|--------------|-----------------------------------|
| Python   | 3.11+        | https://docs.python.org/3/        |
| FastAPI  | latest 0.x   | https://fastapi.tiangolo.com/     |
| httpx    | latest       | https://www.python-httpx.org/     |
| Go (later) | 1.22+      | https://go.dev/doc/                |

## Frontend

| Tech         | Version | Docs                                  |
|--------------|---------|---------------------------------------|
| Node.js      | 20 LTS  | https://nodejs.org/                   |
| Next.js      | 14+     | https://nextjs.org/docs               |
| React        | 18+     | https://react.dev/                    |
| TypeScript   | 5+      | https://www.typescriptlang.org/docs/  |
| Tailwind CSS | 3+      | https://tailwindcss.com/docs          |
| ESLint       | latest  | https://eslint.org/                   |
| Prettier     | latest  | https://prettier.io/                  |

## Database

| Tech       | Version | Docs                                |
|------------|---------|-------------------------------------|
| PostgreSQL | 16      | https://www.postgresql.org/docs/16/ |
| pgvector   | 0.7+    | https://github.com/pgvector/pgvector |

## Automation

| Tech | Version | Docs                       |
|------|---------|----------------------------|
| n8n  | latest  | https://docs.n8n.io/       |

## AI

| Tech            | Version              | Docs                                   |
|-----------------|----------------------|----------------------------------------|
| Claude API      | claude-opus-4-7      | https://docs.claude.com/               |
| Gemini API      | gemini-embedding-001 | https://ai.google.dev/gemini-api/docs  |

**Gemini usage (Lane B):** `gemini-embedding-001` at `output_dimensionality=1536` (L2-normalized) for RAG embeddings; Gemini Flash is the default candidate for query reformulation (R03.1). New provider vs the Claude-only AI table above — the SDK add is "ask first" per CLAUDE.md. See [`../../docs/decisions/lane-b-ml.md`](../../docs/decisions/lane-b-ml.md).

**Orchestration:** direct HTTP calls to the model provider with `asyncio`-based fan-out. No LangChain or LangGraph. See [ADR 0002](../../docs/adr/0002-orchestration-framework.md).

### Model tiers

The agent pipeline uses three tiers. Final picks decided by R&D + user-feedback signal (see [`../agent-pipeline.md`](../agent-pipeline.md)).

| Tier        | Job                                              | Candidates (shortlist)                                                |
|-------------|--------------------------------------------------|-----------------------------------------------------------------------|
| Classifier  | Read incoming email, classify task, emit JSON routing plan. Cheap, fast, must reason well over short text. | Gemma 3B / 7B (self-host), GPT-5 Nano, DeepSeek small                |
| Reasoner    | Sub-tasks: summary, action items, intent extraction. Run **in parallel** — independent. | DeepSeek (strong reasoning), Claude Sonnet, GPT-5                    |
| Drafter     | Generate the reply. Multiple options shown to user; user pick + edit feeds back into selection. | Claude Opus 4.7, Claude Sonnet, DeepSeek, GPT-5                      |

Pin to **3 candidates per tier** during sprint 1; narrow to 1 per tier as thumbs-up/down data accumulates.

**Current implementation:** all tiers run on **Gemini** (`gemini-3.5-flash-lite`) via direct HTTP in
`email_agent.py` — chosen for reliability and speed after HuggingFace-hosted models proved
rate-limited/flaky. The table above stays as the design space to narrow from.

### Anthropic API features in use

- **Prompt caching (mandatory).** The same email-thread context is replayed across the classifier, the three reasoners, and the drafter on every inbound mail. Cache the thread block and the user's `style_profile` block to cut input-token cost by an estimated 70-90%. The 5-minute cache TTL is sufficient for a single pipeline run; no warming strategy is needed for sprint 1.
- **Extended thinking.** Enabled on the drafter tier (Opus 4.7 / Sonnet 4.6) where reply quality justifies the latency. Disabled on the classifier and reasoners where latency dominates and the tasks are short.
