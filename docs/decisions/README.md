# Decision logs

Lightweight, append-only decision logs — one per lane. Whoever owns a lane logs the
decisions and changes they make in it, with the reasoning, so the team can see *why* a
thing is the way it is without asking.

## Relation to ADRs

- `docs/adr/` — **significant** architecture decisions. Reviewed, heavyweight, one file
  per decision (e.g. "no LangGraph", "no chrome extension").
- `docs/decisions/` (here) — the **day-to-day** tier. Schema tweaks, model picks, build
  ordering, seam shapes. Cheap to add; no review gate.

Rule of thumb: if it would change another lane's contract, it is also an ADR and/or a
`specs/` change. If it only shapes your own lane, a log entry here is enough.

## Files

| File | Lane | Good-enough floor |
|---|---|---|
| [`lane-a-spine.md`](lane-a-spine.md) | A · OAuth, ingestion, PII masking, storage + audit | 80% masking accuracy |
| [`lane-b-ml.md`](lane-b-ml.md) | B · RAG pipeline, trained classifier, retrieval metrics | Beat the baseline |
| [`lane-c-generation.md`](lane-c-generation.md) | C · Router, reply + tone, Critic, live logging | 80% Critic confidence |
| [`lane-d-surfaces.md`](lane-d-surfaces.md) | D · Dashboard, extension, eval harness, user testing | Usable + tested |
| [`shared.md`](shared.md) | Cross-lane — schema, CI, seams, thin slice | — |

Lanes are from `AImail_build_split`. Ownership is filled in per file as the team assigns it.

## How to log

Add an entry at the **top** of your lane file (newest first). Copy this block:

```markdown
### YYYY-MM-DD — <short title>
- Decision: <what you decided>
- Why: <the problem it solves>
- Why not <alternative>: <why the other option lost>
- Affects: <seam / spec file / table / issue #>
- Status: proposed | accepted | superseded by <date/title>
```

Keep each field to a line or two. `Why` and `Why not` are not optional — a decision
without its rejected alternative is a note, not a decision.

## Status values

- **proposed** — logged, not yet agreed by whoever it touches.
- **accepted** — agreed; live.
- **superseded** — replaced by a later entry (link it). Never delete old entries; the
  trail is the point.
