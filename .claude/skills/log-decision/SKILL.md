---
name: log-decision
description: Use when a design or architectural decision is made in AImail that should be recorded. Appends a correctly-formatted, dated entry to the right per-lane decision log (or shared.md for cross-lane decisions), with rationale and the alternatives considered.
---

Record the decision in the append-only decision trail. Never edit past entries.

1. Pick the target file: `docs/decisions/lane-<a|b|c|d>.md` for a single-lane decision, or `docs/decisions/shared.md` if it crosses lanes or touches a shared contract.
2. Append a new dated entry matching the existing format:
   - `### <YYYY-MM-DD> - <short title>`
   - `- Decision: <what was decided>`
   - `- Why: <rationale>`
   - `- Why not <alternative>: <reason>` (include the alternatives that were considered)
   - `- Affects: <files / lanes>`
   - `- Status: proposed | accepted`
3. For a cross-lane decision, also update the relevant `specs/context/` contract in the same change.
4. Use today's date; convert any relative dates to absolute.
