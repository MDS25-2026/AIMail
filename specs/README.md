# specs

This folder is the **source of truth** for what AImail does and how. Code follows specs, not the other way around.

## How it works

1. One feature = one file in [`features/`](features/).
2. Copy [`_template.md`](_template.md) when starting a new feature spec. Name it `kebab-case.md` (e.g. `pii-masking.md`).
3. Keep the **Status** field current: `draft` → `approved` → `in-progress` → `shipped` → `archived`.
4. AI agents (Claude Code, etc.) read the relevant spec **before** writing feature code. Humans do the same.
5. If reality diverges from the spec mid-implementation, update the spec in the same PR.

## Layout

```
specs/
├── README.md            # this file
├── _template.md         # copy this for new feature specs
├── architecture.md      # system architecture (4 components, flow)
├── conventions.md       # code style + naming
├── features/            # one .md per feature
└── context/
    ├── api-contracts.md # REST contract between backend ↔ frontend
    ├── db-schema.md     # Postgres schema source of truth
    └── tech-stack.md    # versions + doc links
```

## Rules

> **Phase 0 (current — until first feature ships):** the rules below are aspirational. Specs in `features/` may be `Status: idea` sketches that capture the concept without prescribing implementation. Full specs (template, testable ACs, spec-only PRs) kick in from sprint 2 when features get picked up for build. The relaxation only applies to the spec-first workflow — everything else (commits, branches, reviews) applies in full. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md) stage 2.

- No feature code without an approved spec.
- Specs ship as their own PR (no code), reviewed and merged before implementation begins. Exception: trivially small features may bundle spec + code in one PR if the reviewer is comfortable.
- Cross-cutting concerns (API shape, DB columns) live in `context/`, not duplicated per feature.
- Specs are short. If a spec exceeds two screens, split it.

## Living specs — bidirectional updates

A spec is not a one-time prompt. Information flows **both ways**:

```
intent → spec → code        (forwards: humans tell agents what to build)
intent ← spec ← code        (backwards: implementation reality updates the spec)
```

**Backward updates are mandatory.** If, while implementing, you discover:

- An assumption in the spec was wrong → fix the spec in the same PR.
- An edge case isn't covered → add it to **Edge cases & failure modes**.
- A decision was made that wasn't in the spec → record it in the spec's **Implementation notes** or open an ADR in `docs/adr/`.

Without backward updates, specs are just elaborate prompts. With them, specs become institutional memory the next agent (human or AI) can trust.

## Granularity — declarative, not imperative

Specs describe **outcomes and constraints**, not implementation steps. Compare:

| Imperative (avoid) | Declarative (do this) |
|--------------------|------------------------|
| "Import `numpy`. Define `cosine_distance(a, b)`. Convert inputs to numpy arrays. Return the dot product divided by the product of magnitudes." | "Compute cosine distance between two input vectors. Should be fast and side-effect-free." |
| "Loop over `email.parts`. For each part, check if `mime_type` starts with `text/`. Concatenate body fields..." | "Extract the plain-text body from a multipart email. Prefer `text/plain` parts; fall back to stripped HTML if none exist." |

Imperative specs over-constrain agents and rot when libraries change. Declarative specs let agents apply existing patterns.

**The over-specification trap:** if the spec gets too detailed, agents either ignore it or follow it too literally. Aim for *enough structure to constrain risk*, not *step-by-step instructions*.

**The under-specification trap:** if the spec is too vague ("build a login system"), agents fill gaps with assumptions that often differ from yours.

The middle is "specify the **what** and **why**, plus quantifiable acceptance criteria. Leave the **how** to the implementer."

## Acceptance criteria must be testable

Each AC must be observable, binary, and runnable as a check. The pattern:

> Given **\<state\>**, when **\<action\>**, then **\<observable outcome\>**.

Bad:

- [ ] System should handle empty input gracefully.
- [ ] Latency should be acceptable.

Good:

- [ ] Given an empty email body, when the classifier runs, then it returns `{"task": "noop", "reason": "empty"}` without calling any LLM.
- [ ] Given a 2 KB email, when the agent pipeline runs end-to-end, then total latency is under 60 seconds at p95.

If you can't write the check, the criterion is too vague — sharpen it before approving the spec.

## Anti-patterns to avoid in specs

| Anti-pattern | Why it fails | Fix |
|--------------|--------------|-----|
| Mixed concerns in one section | Reviewers can't tell must-haves from suggestions | Separate functional, non-functional, security, and out-of-scope explicitly |
| Vague success criteria | No clear stopping rule; iteration is arbitrary | Use the testable-AC pattern above |
| Jumping to a solution | Implementer builds the named solution, not the problem | Lead with **Goal** and **Why**; the solution is the implementer's call (within constraints) |
| Token-bloat specs | Long, unfocused context degrades AI agent performance | Keep specs ≤ 2 screens; split if longer |
| Missing context continuity | Future agents repeat resolved debates | Record decisions in `docs/adr/`; link from the spec |
