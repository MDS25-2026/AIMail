---
name: lane-check
description: Use to check whether a change stays within its lane in AImail or crosses into another lane's territory. Maps changed files to lanes, flags cross-lane touches that need a shared.md entry and owner review, and flags ask-first actions.
---

Check lane boundaries against AImail's ownership rules (CLAUDE.md).

1. List the changed/added files (`git status --short` and the diff).
2. Map each to its lane by folder:
   - `n8n/` = n8n · `listener/` = Lane A · `frontend/` = Lane D · `infra/` = infra
   - `backend/` = shared by Lane B and Lane C - `app/rag/`, `app/ml/`, `app/db/` are Lane B; `app/agents/` and generation are Lane C
   - `specs/`, `docs/` = shared
3. Report:
   - Which lane(s) the change touches.
   - Any change to **another lane's folder** - flag it as "ask first"; the owner must review.
   - Any change to a **shared contract** (`specs/context/api-contracts.md`, `db-schema.md`) or to **more than one service** - must be logged in `docs/decisions/shared.md`.
   - Any **ask-first action**: a new dependency (pip / npm / go get), a REST or DB-schema change, a CI change, or repo settings.
4. If the change is cleanly within one lane and touches no shared contract, say so plainly.
