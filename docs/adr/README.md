# Architecture Decision Records

This folder records architectural decisions made on AImail. One file per decision, numbered in order.

ADRs capture the **why** behind a choice — the alternatives considered, the trade-offs accepted, the conditions under which the decision should be revisited. They are the antidote to "I don't remember why we did it that way" six months later.

## When to write an ADR

Open an ADR when a decision:

- Affects more than one component (cross-cutting).
- Picks one of several plausible options where reasonable people would disagree.
- Locks in a non-trivial constraint future work must respect.
- Was made by the team after discussion (so future joiners see the reasoning).

Don't write ADRs for:

- Decisions internal to one feature → record in that feature's spec under **Decisions**.
- Trivial tooling preferences (linter rules, file paths) → record in `specs/conventions.md`.
- Stylistic choices → record in `specs/conventions.md`.

## Status values

| Status     | Meaning |
|------------|---------|
| Proposed   | Open for discussion. Not yet binding. |
| Accepted   | Decision is in force. Implementations follow it. |
| Rejected   | Considered and explicitly declined. Recorded so the question doesn't get re-litigated. |
| Superseded | Replaced by a later ADR. Link to the successor. |
| Deprecated | No longer applies (e.g., the constraint went away). Kept for history. |

## Format

Each ADR follows the structure used by ADRs 0001 onward:

- **Title** — short descriptive name.
- **Status / Date / Deciders / Supersedes** — metadata.
- **Context** — why this decision is being made.
- **Decision** — the choice itself, in one or two sentences.
- **Rationale** — why this option won.
- **Alternatives considered** — what else was on the table, why each lost.
- **Consequences** — positive and negative effects we're accepting.
- **Revisit conditions** — what would make us re-open this.

## Index

| #    | Title                                                                          | Status                              |
|------|--------------------------------------------------------------------------------|-------------------------------------|
| 0001 | [No Chrome extension for AImail v1](0001-no-chrome-extension.md)               | Accepted                            |
| 0002 | [Orchestration framework choice (LangChain vs. direct SDK)](0002-orchestration-framework.md) | Proposed — pending team meeting |

## Numbering

ADRs are numbered sequentially in **decision order**, not insertion order. The next ADR is `0003-*.md`. Don't reuse numbers, even for rejected ADRs.

## Cross-references

ADRs are linked from:

- The relevant spec under its **Decisions** section.
- `CLAUDE.md` if the decision constrains agent behavior.
- `specs/architecture.md` if the decision shapes the high-level architecture.

When you write a new ADR, update this index and any docs that should reference it.
