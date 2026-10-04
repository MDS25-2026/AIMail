# infra

Infrastructure, deployment, and local-dev orchestration for AImail. Houses Docker Compose files, database init scripts, and (later) IaC for the deployment target.

**Set up now:** the Gmail notification dead-letter policy, [`pubsub-dead-letter.md`](pubsub-dead-letter.md). The rest of this README predates the current stack (Compose lives at the repo root) and is due a rewrite.

## Run locally

_Not built yet._ Placeholder steps:

```bash
cd infra
docker compose up -d        # TODO — postgres + pgvector + n8n
```

## Key dependencies

- Docker + Docker Compose
- PostgreSQL 16 + `pgvector` extension
- n8n (containerised)

## Env vars

A root `.env.example` will document the shared envs Compose reads. TODO.

## Folder structure

```
infra/
├── docker-compose.yml       # TODO — local stack (postgres, n8n)
├── postgres/
│   └── init.sql             # TODO — create db, enable pgvector
├── n8n/                     # n8n persistent volume mount config
└── deploy/                  # cloud deployment config (later)
```
