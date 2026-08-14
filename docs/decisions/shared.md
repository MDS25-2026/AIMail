# Shared — cross-lane decisions

Schema, CI, seams, the thin slice, and anything touching more than one lane. Everyone logs
here when their change crosses a lane boundary. Schema and public contracts are "ask first"
(both CLAUDE.md files) — log the decision here *and* update `specs/context/` in the same PR.

## Log

### 2026-07-07 — Schema authority order for reconciliation
- Decision: when the pasted research, the repo design specs, and the proposal report
  disagree, resolve as: **proposal R-IDs = fixed contract > repo design specs (in flux) >
  research (one input)**.
- Why: the proposal is the graded, submitted team contract; the repo specs are a scaffold
  that has already drifted (see below); the research is one member's external exploration.
- Affects: `specs/context/db-schema.md`, all lane schemas.
- Status: proposed
- Reference: full reconciled schema drafted in scratchpad (not yet committed to db-schema.md).

### 2026-07-07 — Repo drift found while reading specs (needs team decision)
- Decision: none yet — flagging two stale/contradictory spots.
  1. `specs/architecture.md` describes `Gmail -> n8n -> listener`; proposal moved to
     **Go webhook + Pub/Sub** (Table 3 marks n8n "prototyping only"; `main.go` is a draft
     webhook). Architecture.md needs updating to match, or the migration finished.
  2. ADR 0001 "no chrome extension" contradicts **R04.5** (chrome extension required).
- Why logged: both were written into the repo before the proposal's final architecture; a
  new session would trust the stale version.
- Affects: architecture.md, ADR 0001, Lane A + Lane D.
- Status: proposed — raise at next sprint planning.

### 2026-08-06 — Integration sync: divergences found across lane branches
- Context: first sync; `main` still on scaffold, all four lanes on their own branches (none merged).
- Found:
  1. **Seam 1 field mismatch (blocking):** Lane A (JiaJun) persists `body_masked`; Lane B expects
     `masked_body`. Align on one name — recommend `body_masked` (Lane A owns the email table).
  2. **Two frontends:** Han's Vite dashboard vs the Next.js scaffold. Keep Han's; retire the scaffold.
  3. **Two listeners:** JiaJun's Go listener vs the Python stub. Keep Go; retire the stub.
  4. **DB access split:** Lane A writes via Supabase PostgREST (`SUPABASE_SERVICE_KEY`); Lane B reads
     via asyncpg (`DATABASE_URL`). Same project required; column names must match in `db-schema.md`.
  5. **One shared Supabase project** — all lanes must point at the same project or writes/reads never meet.
- Status: proposed — resolve at the sync meeting. Reflected in `specs/architecture.md`.

### 2026-07-30 — Lane B demo endpoints recorded in api-contracts (provisional)
- Decision: documented `/search`, `/ask`, `GET|POST /documents`, `/documents/upload` in
  `specs/context/api-contracts.md` as a **provisional** Lane B demo surface, not the finalised contract.
- Why: they exist in `backend/app/main.py` (the retrieval demo) and were undocumented — real drift.
  Recording them lets Lane C/D see the shapes; final shapes/auth/error-envelope get pinned with Lane D.
- Why not treat as final: they skip the `{error:{...}}` envelope and have no auth; that alignment is a
  follow-up when the contract is agreed.
- Affects: `specs/context/api-contracts.md`, Lane B, Lane D.
- Status: proposed

### 2026-07-07 — Decision-log convention created
- Decision: per-lane append-only logs under `docs/decisions/`, lighter tier below ADRs.
- Why: a lane's rationale trail survives reassignment (build-split reopened ownership);
  one owner per lane makes it effectively per-person without breaking on a swap.
- Why not per-person files: they break the moment a lane is reassigned.
- Affects: repo docs convention.
- Status: accepted
